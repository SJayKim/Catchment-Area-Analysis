import { create } from 'zustand';
import { ChatMessage, SSEEvent, AgentStep } from '@/lib/types';
import { sendChatMessage } from '@/lib/api';

const TOOL_LABELS: Record<string, { progress: string; done: string; icon: string }> = {
  get_floating_population_tool: { progress: '유동인구 조회 중...', done: '유동인구 조회 완료', icon: '🔍' },
  get_estimated_sales_tool: { progress: '추정매출 조회 중...', done: '추정매출 조회 완료', icon: '🔍' },
  get_store_info_tool: { progress: '점포 현황 조회 중...', done: '점포 현황 조회 완료', icon: '🔍' },
  get_population_info_tool: { progress: '인구 데이터 조회 중...', done: '인구 데이터 조회 완료', icon: '🔍' },
  get_district_summary_tool: { progress: '상권 요약 생성 중...', done: '상권 요약 생성 완료', icon: '📋' },
  compare_districts_tool: { progress: '상권 비교 분석 중...', done: '상권 비교 분석 완료', icon: '📊' },
  recommend_business_tool: { progress: '업종 추천 분석 중...', done: '업종 추천 분석 완료', icon: '💡' },
  get_store_history_tool: { progress: '점포 이력 분석 중...', done: '점포 이력 분석 완료', icon: '📋' },
};

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

  /** Core sendMessage action — single instance, no closure issues */
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

    // Resolve district code with fallback
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

    let firstTextReceived = false;

    try {
      const response = await sendChatMessage(
        message.trim(),
        state.sessionId,
        resolvedDistrictCode
      );

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6).trim();
          if (!data || data === '[DONE]') continue;

          try {
            const event: SSEEvent = JSON.parse(data);
            handleSSEEvent(event, onMapCmd);
          } catch {
            // Skip malformed JSON
          }
        }
      }

      // Process remaining buffer
      if (buffer.startsWith('data: ')) {
        const data = buffer.slice(6).trim();
        if (data && data !== '[DONE]') {
          try {
            const event: SSEEvent = JSON.parse(data);
            handleSSEEvent(event, onMapCmd);
          } catch {
            // Skip malformed JSON
          }
        }
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

    function handleSSEEvent(
      event: SSEEvent,
      onMapCmd?: (event: SSEEvent) => void
    ) {
      switch (event.type) {
        case 'thinking': {
          set({ isThinking: true });
          const currentSteps = get().agentSteps;
          if (currentSteps.length === 0) {
            // First thinking — "🧠 질문 분석 중..."
            get().addAgentStep({
              id: 'thinking',
              label: '🧠 질문 분석 중...',
              status: 'in_progress',
            });
          } else {
            // Subsequent thinking (after tool calls) — "💬 응답 작성 중..."
            const hasResponseStep = currentSteps.some((s) => s.id === 'response');
            if (!hasResponseStep) {
              get().addAgentStep({
                id: 'response',
                label: '💬 응답 작성 중...',
                status: 'in_progress',
              });
            }
          }
          break;
        }

        case 'tool': {
          // Complete thinking step
          get().updateAgentStepStatus('thinking', 'completed', '🧠 질문 분석 완료');
          // Add new tool step
          const toolName = event.name as string;
          const toolLabel = TOOL_LABELS[toolName];
          const icon = toolLabel?.icon || '🔧';
          get().addAgentStep({
            id: `tool-${toolName}`,
            label: `${icon} ${toolLabel?.progress || `${toolName} 실행 중...`}`,
            status: 'in_progress',
            toolName,
          });
          break;
        }

        case 'tool_end': {
          const endToolName = event.name as string;
          const endLabel = TOOL_LABELS[endToolName];
          const endIcon = endLabel?.icon || '🔧';
          get().updateAgentStepStatus(
            `tool-${endToolName}`,
            'completed',
            `${endIcon} ${endLabel?.done || `${endToolName} 완료`}`
          );
          break;
        }

        case 'text':
          if (!firstTextReceived) {
            firstTextReceived = true;
            // Complete all remaining in_progress steps
            const steps = get().agentSteps;
            for (const step of steps) {
              if (step.status === 'in_progress') {
                get().updateAgentStepStatus(step.id, 'completed');
              }
            }
            // Add "✅ 분석 완료" final step
            get().addAgentStep({
              id: 'final',
              label: '✅ 분석 완료',
              status: 'completed',
            });
            // Keep steps visible so user can see the full progress, then fade out
            setTimeout(() => {
              set({ agentSteps: [], isThinking: false });
            }, 1500);
          }
          get().updateLastAssistantMessage(event.content as string);
          break;

        case 'card': {
          // Update progress: mark thinking as complete, add card step
          get().updateAgentStepStatus('thinking', 'completed', '🧠 질문 분석 완료');
          const cardType = event.card_type as string;
          const cardLabel = cardType === 'summary' ? '상권 요약 카드'
            : cardType === 'compare' ? '비교 분석 카드'
            : cardType === 'recommend' ? '업종 추천 카드'
            : cardType === 'risk' ? '리스크 분석 카드'
            : '분석 카드';
          get().addAgentStep({
            id: `card-${cardType}`,
            label: `📊 ${cardLabel} 생성 완료`,
            status: 'completed',
          });

          const cardMessage: ChatMessage = {
            id: generateId(),
            role: 'assistant',
            content: '',
            type: 'card',
            cardType,
            cardData: event.data as Record<string, unknown>,
            timestamp: new Date(),
          };
          set((s) => ({ messages: [...s.messages, cardMessage] }));
          break;
        }

        case 'map_cmd': {
          if (event.district_code) {
            set({ lastDistrictCode: event.district_code as string });
          }
          onMapCmd?.(event);
          break;
        }

        case 'suggestion':
          set({ suggestions: event.questions as string[] });
          break;

        case 'done':
          set({ isLoading: false });
          // agentSteps cleanup is handled by the text event's setTimeout
          // Only clear if no text was received (edge case)
          if (!firstTextReceived) {
            set({ isThinking: false, agentSteps: [] });
          }
          break;

        case 'error':
          set({ isThinking: false, agentSteps: [] });
          get().updateLastAssistantMessage(
            (event.message as string) || '오류가 발생했습니다.'
          );
          break;
      }
    }
  },
}));
