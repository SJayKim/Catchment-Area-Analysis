import { ChatMessage, SSEEvent, AgentStep } from './types';

export const TOOL_LABELS: Record<string, { progress: string; done: string; icon: string }> = {
  get_floating_population_tool: { progress: '유동인구 조회 중...', done: '유동인구 조회 완료', icon: '🔍' },
  get_estimated_sales_tool: { progress: '추정매출 조회 중...', done: '추정매출 조회 완료', icon: '🔍' },
  get_store_info_tool: { progress: '점포 현황 조회 중...', done: '점포 현황 조회 완료', icon: '🔍' },
  get_population_info_tool: { progress: '인구 데이터 조회 중...', done: '인구 데이터 조회 완료', icon: '🔍' },
  get_district_summary_tool: { progress: '상권 요약 생성 중...', done: '상권 요약 생성 완료', icon: '📋' },
  compare_districts_tool: { progress: '상권 비교 분석 중...', done: '상권 비교 분석 완료', icon: '📊' },
  recommend_business_tool: { progress: '업종 추천 분석 중...', done: '업종 추천 분석 완료', icon: '💡' },
  get_store_history_tool: { progress: '점포 이력 분석 중...', done: '점포 이력 분석 완료', icon: '📋' },
  simulate_revenue_tool: { progress: '매출 시뮬레이션 중...', done: '매출 시뮬레이션 완료', icon: '💰' },
  simulate_revenue: { progress: '매출 시뮬레이션 중...', done: '매출 시뮬레이션 완료', icon: '💰' },
};

const CARD_LABELS: Record<string, string> = {
  summary: '상권 요약 카드',
  compare: '비교 분석 카드',
  recommend: '업종 추천 카드',
  risk: '리스크 분석 카드',
  simulation: '매출 시뮬레이션 카드',
};

function generateId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/** Context provided by chatStore to event handlers. */
export interface EventHandlerContext {
  get: () => {
    agentSteps: AgentStep[];
    addAgentStep: (step: AgentStep) => void;
    updateAgentStepStatus: (id: string, status: AgentStep['status'], label?: string) => void;
    updateLastAssistantMessage: (content: string) => void;
  };
  set: (partial: Record<string, unknown>) => void;
  firstTextReceived: { current: boolean };
  onMapCmd?: (event: SSEEvent) => void;
}

export function handleSSEEvent(event: SSEEvent, ctx: EventHandlerContext): void {
  const { get, set } = ctx;

  switch (event.type) {
    case 'thinking': {
      set({ isThinking: true });
      const currentSteps = get().agentSteps;
      if (currentSteps.length === 0) {
        get().addAgentStep({ id: 'thinking', label: '🧠 질문 분석 중...', status: 'in_progress' });
      } else {
        const hasResponseStep = currentSteps.some((s) => s.id === 'response');
        if (!hasResponseStep) {
          get().addAgentStep({ id: 'response', label: '💬 응답 작성 중...', status: 'in_progress' });
        }
      }
      break;
    }

    case 'plan': {
      // PAE mode: Planner has classified intent and generated a tool plan
      const intentLabels: Record<string, string> = {
        summary: '📋 상권 요약 분석',
        comparison: '📊 상권 비교 분석',
        recommendation: '💡 업종 추천 분석',
        risk: '⚠ 리스크 분석',
        category_analysis: '🔍 업종별 상세 분석',
        simulation: '💰 매출 시뮬레이션',
        follow_up: '💬 추가 분석',
        general: '💬 일반 응답',
        ambiguous: '❓ 질문 확인',
      };
      const intent = (event as { intent?: string }).intent || '';
      const steps = (event as { steps?: string[] }).steps || [];

      // Complete the thinking step
      const thinkingStep = get().agentSteps.find((s) => s.status === 'in_progress');
      if (thinkingStep) {
        get().updateAgentStepStatus(thinkingStep.id, 'completed', intentLabels[intent] || '분석 계획 수립 완료');
      }

      // Add planned steps as pending
      steps.forEach((label, i) => {
        get().addAgentStep({
          id: `plan-step-${Date.now()}-${i}`,
          label: `📋 ${label}`,
          status: 'pending',
        });
      });
      break;
    }

    case 'tool': {
      get().updateAgentStepStatus('thinking', 'completed', '🧠 질문 분석 완료');
      const toolLabel = TOOL_LABELS[event.name];
      const icon = toolLabel?.icon || '🔧';
      get().addAgentStep({
        id: `tool-${event.name}`,
        label: `${icon} ${toolLabel?.progress || `${event.name} 실행 중...`}`,
        status: 'in_progress',
        toolName: event.name,
      });
      break;
    }

    case 'tool_end': {
      const endLabel = TOOL_LABELS[event.name];
      const endIcon = endLabel?.icon || '🔧';
      get().updateAgentStepStatus(
        `tool-${event.name}`, 'completed',
        `${endIcon} ${endLabel?.done || `${event.name} 완료`}`
      );
      break;
    }

    case 'text': {
      if (!ctx.firstTextReceived.current) {
        ctx.firstTextReceived.current = true;
        const steps = get().agentSteps;
        for (const step of steps) {
          if (step.status === 'in_progress') {
            get().updateAgentStepStatus(step.id, 'completed');
          }
        }
        get().addAgentStep({ id: 'final', label: '✅ 분석 완료', status: 'completed' });
        setTimeout(() => { set({ agentSteps: [], isThinking: false }); }, 1500);
      }
      get().updateLastAssistantMessage(event.content);
      break;
    }

    case 'card': {
      get().updateAgentStepStatus('thinking', 'completed', '🧠 질문 분석 완료');
      const cardLabel = CARD_LABELS[event.card_type] || '분석 카드';
      get().addAgentStep({
        id: `card-${event.card_type}`,
        label: `📊 ${cardLabel} 생성 완료`,
        status: 'completed',
      });
      const cardMessage: ChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: '',
        type: 'card',
        cardType: event.card_type,
        cardData: event.data,
        timestamp: new Date(),
      };
      set({ messages: [...(get() as unknown as { messages: ChatMessage[] }).messages, cardMessage] });
      break;
    }

    case 'map_cmd': {
      if (event.district_code) {
        set({ lastDistrictCode: event.district_code });
      }
      ctx.onMapCmd?.(event);
      break;
    }

    case 'suggestion':
      set({ suggestions: event.questions });
      break;

    case 'done':
      set({ isLoading: false });
      if (!ctx.firstTextReceived.current) {
        set({ isThinking: false, agentSteps: [] });
      }
      break;

    case 'error':
      set({ isThinking: false, agentSteps: [] });
      get().updateLastAssistantMessage(event.message || '오류가 발생했습니다.');
      break;
  }
}
