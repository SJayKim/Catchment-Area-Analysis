import { create } from 'zustand';
import { ChatMessage, SSEEvent, AgentStep } from '@/lib/types';
import { sendChatMessage } from '@/lib/api';
import { parseSSEStream } from '@/lib/sseParser';
import { handleSSEEvent, EventHandlerContext } from '@/lib/eventHandlers';

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

interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  isThinking: boolean;
  sessionId: string;
  suggestions: string[];
  lastDistrictCode: string | null;
  agentSteps: AgentStep[];
  currentAbortController: AbortController | null;

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
    if (!message.trim() || state.isLoading) return;

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
    set((s) => ({ messages: [...s.messages, userMessage] }));
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

    const firstTextReceived = { current: false };
    const ctx: EventHandlerContext = {
      get: get as EventHandlerContext['get'],
      set: (partial) => set(partial as Partial<ChatState>),
      firstTextReceived,
      onMapCmd,
    };

    // Abort any in-flight request so a new send cancels the old stream
    // cleanly on both network (fetch signal) and reader (finally cancel)
    // sides. The server-side disconnect detection (P0-4) then cancels the
    // LangGraph task.
    const prior = get().currentAbortController;
    if (prior) {
      prior.abort();
    }
    const controller = new AbortController();
    set({ currentAbortController: controller });

    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    try {
      const response = await sendChatMessage(
        message.trim(),
        state.sessionId,
        resolvedDistrictCode,
        controller.signal
      );
      reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      for await (const event of parseSSEStream(reader)) {
        handleSSEEvent(event, ctx);
      }
    } catch (err) {
      // Intentional cancellation from a subsequent sendMessage — don't
      // surface as an error bubble.
      const isAbort =
        err instanceof DOMException && err.name === 'AbortError';
      if (!isAbort) {
        const errorMessage: ChatMessage = {
          id: generateId(),
          role: 'assistant',
          content:
            '죄송합니다. 요청을 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
          type: 'error',
          timestamp: new Date(),
        };
        set((s) => ({ messages: [...s.messages, errorMessage] }));
      }
    } finally {
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
