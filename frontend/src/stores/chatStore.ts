import { create } from 'zustand';
import { ChatMessage } from '@/lib/types';

function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  isThinking: boolean;
  sessionId: string;
  suggestions: string[];
  addMessage: (message: ChatMessage) => void;
  updateLastAssistantMessage: (content: string) => void;
  setLoading: (loading: boolean) => void;
  setThinking: (thinking: boolean) => void;
  setSuggestions: (suggestions: string[]) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isLoading: false,
  isThinking: false,
  sessionId: generateUUID(),
  suggestions: [
    '이 상권의 유동인구 알려줘',
    '여기서 뭐하면 좋을까?',
    '주요 업종 현황 보여줘',
  ],

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

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

  clearMessages: () =>
    set({
      messages: [],
      sessionId: generateUUID(),
      suggestions: [
        '이 상권의 유동인구 알려줘',
        '여기서 뭐하면 좋을까?',
        '주요 업종 현황 보여줘',
      ],
    }),
}));
