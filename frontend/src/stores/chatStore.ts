import { create } from 'zustand';
import { ChatMessage, SSEEvent, AgentStep } from '@/lib/types';
import {
  sendChatMessage,
  fetchDistrictPreview,
  DistrictPreview,
} from '@/lib/api';
import { parseSSEStream } from '@/lib/sseParser';
import { handleSSEEvent, EventHandlerContext } from '@/lib/eventHandlers';

export type UserRole = 'owner' | 'investor' | 'founder';
export type MobileTab = 'map' | 'chat';
export type SheetSnap = 'hidden' | 'peek' | 'half' | 'full';
const VALID_ROLES: UserRole[] = ['owner', 'investor', 'founder'];
function isRole(v: unknown): v is UserRole {
  return typeof v === 'string' && (VALID_ROLES as string[]).includes(v);
}

function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function generateId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * Module-private state for setPreview race protection.
 *
 * Problem: when the user clicks district A then quickly clicks B, two
 * fetches race. The previous lastDistrictCode-based guard picked up the
 * *first-arriving* response and dropped the latest one — exactly backwards.
 *
 * Solution: a monotonic sequence counter + AbortController. The latest
 * caller wins, in-flight earlier requests are cancelled, and any response
 * whose seq != _previewSeq is silently dropped.
 */
let _previewSeq = 0;
let _previewAbort: AbortController | null = null;

interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  isThinking: boolean;
  sessionId: string;
  suggestions: string[];
  lastDistrictCode: string | null;
  agentSteps: AgentStep[];
  currentAbortController: AbortController | null;
  /**
   * Monotonic counter incremented at the start of every sendMessage. SSE
   * event handlers compare ctx.requestId against this value and discard
   * stale events from previously aborted streams. See
   * docs/plan/fix/district-click-race-2026-04-28.md §3.1.2.
   */
  currentRequestId: number;
  role: UserRole | null;
  preview: DistrictPreview | null;
  previewLoading: boolean;
  previewError: string | null;
  messageCount: number;
  lastTraceId: string | null;
  /** trace_id → 피드백 제출 여부. 세션당 trace 당 1회 제한 (스팸 가드). */
  feedbackByTrace: Record<string, 'up' | 'down'>;

  mobileTab: MobileTab;
  sheetSnap: SheetSnap;
  unreadCount: number;
  setMobileTab: (tab: MobileTab) => void;
  setSheetSnap: (snap: SheetSnap) => void;
  incrementUnread: () => void;
  resetUnread: () => void;

  addMessage: (message: ChatMessage) => void;
  updateLastAssistantMessage: (content: string) => void;
  setLoading: (loading: boolean) => void;
  setThinking: (thinking: boolean) => void;
  setSuggestions: (suggestions: string[]) => void;
  setLastDistrictCode: (code: string | null) => void;
  clearMessages: () => void;
  clearAgentSteps: () => void;
  addAgentStep: (step: AgentStep) => void;
  updateAgentStepStatus: (id: string, status: AgentStep['status'], label?: string) => void;

  setRole: (role: UserRole | null) => void;
  setPreview: (code: string) => Promise<void>;
  clearPreview: () => void;
  setLastTraceId: (traceId: string | null) => void;
  recordFeedback: (traceId: string, value: 'up' | 'down') => void;

  sendMessage: (
    message: string,
    districtCode?: string,
    onMapCmd?: (event: SSEEvent) => void
  ) => Promise<void>;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isLoading: false,
  isThinking: false,
  sessionId: generateUUID(),
  suggestions: [
    '이 상권의 유동인구 알려줘',
    '여기서 뭐하면 좋을까?',
    '주요 업종 현황 보여줘',
  ],
  lastDistrictCode: null,
  agentSteps: [],
  currentAbortController: null,
  currentRequestId: 0,
  role: null,
  preview: null,
  previewLoading: false,
  previewError: null,
  messageCount: 0,
  lastTraceId: null,
  feedbackByTrace: {},

  mobileTab: 'map',
  sheetSnap: 'hidden',
  unreadCount: 0,
  setMobileTab: (tab) =>
    set((s) => ({
      mobileTab: tab,
      // 챗 탭 활성화 시 뱃지 초기화
      unreadCount: tab === 'chat' ? 0 : s.unreadCount,
    })),
  setSheetSnap: (snap) => set({ sheetSnap: snap }),
  incrementUnread: () => set((s) => ({ unreadCount: s.unreadCount + 1 })),
  resetUnread: () => set({ unreadCount: 0 }),

  setRole: (role) => set({ role: isRole(role) ? role : null }),

  setLastTraceId: (traceId) => set({ lastTraceId: traceId }),

  recordFeedback: (traceId, value) =>
    set((s) => ({ feedbackByTrace: { ...s.feedbackByTrace, [traceId]: value } })),

  setPreview: async (code) => {
    // Cancel any in-flight preview fetch and bump the sequence.
    _previewAbort?.abort();
    const ac = new AbortController();
    _previewAbort = ac;
    const seq = ++_previewSeq;

    set({ previewLoading: true, previewError: null });
    try {
      const role = get().role ?? undefined;
      const preview = await fetchDistrictPreview(code, role, ac.signal);
      // A newer setPreview call has won the race — discard this response.
      if (seq !== _previewSeq) return;
      set({ preview, previewLoading: false, lastDistrictCode: code });
    } catch (err) {
      // Intentional cancellation by a newer click — silent drop.
      if (ac.signal.aborted) return;
      if (seq !== _previewSeq) return;
      const msg = err instanceof Error ? err.message : 'preview failed';
      set({ preview: null, previewError: msg, previewLoading: false });
    }
  },

  clearPreview: () => set({ preview: null, previewError: null }),

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),

  updateLastAssistantMessage: (content) =>
    set((state) => {
      const messages = [...state.messages];
      for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].role === 'assistant' && messages[i].type !== 'card') {
          messages[i] = { ...messages[i], content: messages[i].content + content };
          break;
        }
      }
      return { messages };
    }),

  setLoading: (loading) => set({ isLoading: loading }),
  setThinking: (thinking) => set({ isThinking: thinking }),
  setSuggestions: (suggestions) => set({ suggestions }),
  setLastDistrictCode: (code) => set({ lastDistrictCode: code }),

  clearMessages: () =>
    set({
      messages: [],
      sessionId: generateUUID(),
      lastDistrictCode: null,
      agentSteps: [],
      preview: null,
      previewError: null,
      messageCount: 0,
      currentRequestId: 0,
      suggestions: [
        '이 상권의 유동인구 알려줘',
        '여기서 뭐하면 좋을까?',
        '주요 업종 현황 보여줘',
      ],
    }),

  clearAgentSteps: () => set({ agentSteps: [] }),

  addAgentStep: (step) =>
    set((state) => ({ agentSteps: [...state.agentSteps, step] })),

  updateAgentStepStatus: (id, status, label) =>
    set((state) => ({
      agentSteps: state.agentSteps.map((s) =>
        s.id === id ? { ...s, status, ...(label ? { label } : {}) } : s
      ),
    })),

  sendMessage: async (message, districtCode, onMapCmd) => {
    const state = get();
    if (!message.trim()) return;

    // Pre-empt any in-flight stream so a new send (e.g. user clicked a
    // different district mid-stream) cancels the old one and starts fresh.
    // The previous stream's finally block sees a different controller (set
    // below) and skips state cleanup; the previous stream's late SSE events
    // are filtered by the requestId staleness guard in eventHandlers.
    if (state.isLoading && state.currentAbortController) {
      state.currentAbortController.abort();
    }

    // 모바일: 사용자가 질문을 보내는 순간 챗 탭 + full snap 으로 승격.
    // (데스크톱은 SplitPanel 이라 mobileTab/sheetSnap 의미 없음 — 비용 0)
    if (state.mobileTab !== 'chat') set({ mobileTab: 'chat', unreadCount: 0 });
    if (state.sheetSnap !== 'full') set({ sheetSnap: 'full' });

    // PDF export pattern detection — handle locally, don't send to server
    const PDF_PATTERNS = /pdf|리포트.*저장|보고서.*내보|리포트.*만들|보고서.*만들|리포트.*내려|pdf.*저장/i;
    if (PDF_PATTERNS.test(message.trim())) {
      const userMsg: ChatMessage = {
        id: generateId(),
        role: 'user',
        content: message.trim(),
        type: 'text',
        timestamp: new Date(),
      };
      set((s) => ({ messages: [...s.messages, userMsg] }));

      const assistantMsg: ChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: 'PDF 리포트를 생성 중입니다... 상단의 PDF 버튼을 클릭하시면 다운로드됩니다.',
        type: 'text',
        timestamp: new Date(),
      };
      set((s) => ({ messages: [...s.messages, assistantMsg] }));

      // Trigger PDF generation via custom event
      window.dispatchEvent(new CustomEvent('marketscope:generate-pdf'));
      return;
    }

    const resolvedDistrictCode = districtCode ?? state.lastDistrictCode ?? undefined;

    // Add user message
    const userMessage: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: message.trim(),
      type: 'text',
      timestamp: new Date(),
    };
    set((s) => ({
      messages: [...s.messages, userMessage],
      messageCount: s.messageCount + 1,
      // Preview is implicit, drop it once the user engages the full pipeline
      preview: null,
      previewError: null,
    }));
    set({ isLoading: true, isThinking: true, agentSteps: [
      { id: 'thinking', label: '질문 분석 중...', status: 'in_progress' },
    ] });

    // Add empty assistant message placeholder
    const assistantMessage: ChatMessage = {
      id: generateId(),
      role: 'assistant',
      content: '',
      type: 'text',
      timestamp: new Date(),
    };
    set((s) => ({ messages: [...s.messages, assistantMessage] }));

    // Allocate a monotonic request id so staleness-aware event handlers can
    // discard SSE events that arrive after a newer send has started.
    const requestId = get().currentRequestId + 1;
    const firstTextReceived = { current: false };
    const ctx: EventHandlerContext = {
      get: get as EventHandlerContext['get'],
      set: (partial) => set(partial as Partial<ChatState>),
      firstTextReceived,
      onMapCmd,
      requestId,
    };

    // Abort any in-flight request so a new send cancels the old stream
    // cleanly on both network (fetch signal) and reader (finally cancel)
    // sides. The server-side disconnect detection (P0-4) then cancels the
    // LangGraph task. (Defensive — already aborted at function entry.)
    const prior = get().currentAbortController;
    if (prior) {
      prior.abort();
    }
    const controller = new AbortController();
    set({ currentAbortController: controller, currentRequestId: requestId });

    const MAX_RETRIES = 2;
    const BASE_DELAY_MS = 1000;
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    let succeeded = false;

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        const response = await sendChatMessage(
          message.trim(),
          state.sessionId,
          resolvedDistrictCode,
          controller.signal
        );

        // Don't retry client errors (4xx)
        if (response.status >= 400 && response.status < 500) {
          throw new Error(`Client error: ${response.status}`);
        }

        reader = response.body?.getReader();
        if (!reader) throw new Error('No response body');

        // SSE stream timeout: reset on each event, abort if idle > 120s
        let streamTimer: ReturnType<typeof setTimeout> | undefined;
        const resetStreamTimer = () => {
          if (streamTimer) clearTimeout(streamTimer);
          streamTimer = setTimeout(() => {
            controller.abort();
          }, 120_000);
        };
        resetStreamTimer();

        for await (const event of parseSSEStream(reader)) {
          resetStreamTimer();
          handleSSEEvent(event, ctx);
        }

        if (streamTimer) clearTimeout(streamTimer);
        succeeded = true;
        break; // Success, exit retry loop
      } catch (err) {
        // Intentional cancellation — never retry
        const isAbort =
          err instanceof DOMException && err.name === 'AbortError';
        if (isAbort) throw err;

        // Last attempt — surface the error
        if (attempt === MAX_RETRIES) {
          const errorMessage: ChatMessage = {
            id: generateId(),
            role: 'assistant',
            content:
              '죄송합니다. 요청을 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
            type: 'error',
            timestamp: new Date(),
          };
          set((s) => ({ messages: [...s.messages, errorMessage] }));
          break;
        }

        // Retry with exponential backoff
        const delay = BASE_DELAY_MS * Math.pow(2, attempt);
        set({ agentSteps: [
          { id: 'retry', label: `재연결 중... (${attempt + 1}/${MAX_RETRIES})`, status: 'in_progress' },
        ] });
        await new Promise((r) => setTimeout(r, delay));

        // Release reader before retry
        if (reader) {
          try { await reader.cancel(); } catch { /* ignore */ }
          reader = undefined;
        }
      }
    }

    // Legacy catch path for AbortError
    if (!succeeded) {
      // Error already handled above
    }

    // finally block (always runs)
    {
      // Release network resources even on abort / error.
      if (reader) {
        try {
          await reader.cancel();
        } catch {
          /* already cancelled — ignore */
        }
      }
      // Only clear the controller if it's still ours — a newer send may
      // have replaced it already.
      if (get().currentAbortController === controller) {
        set({
          currentAbortController: null,
          isLoading: false,
          isThinking: false,
          agentSteps: [],
        });
      }
    }
  },
}));

// Expose for E2E tests (Playwright) — same pattern as districtStore. Used to
// seed `lastTraceId` / `messageCount` without driving the full SSE pipeline.
if (typeof window !== 'undefined') {
  (window as unknown as { __chatStore?: typeof useChatStore }).__chatStore =
    useChatStore;
}
