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
      { id: 'thinking', label: '🧠 질문 분석 중...', status: 'in_progress' },
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

    try {
      const response = await sendChatMessage(message.trim(), state.sessionId, resolvedDistrictCode);
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      for await (const event of parseSSEStream(reader)) {
        handleSSEEvent(event, ctx);
      }
    } catch {
      const errorMessage: ChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: '죄송합니다. 요청을 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
        type: 'error',
        timestamp: new Date(),
      };
      set((s) => ({ messages: [...s.messages, errorMessage] }));
    } finally {
      set({ isLoading: false, isThinking: false, agentSteps: [] });
    }
  },
}));
