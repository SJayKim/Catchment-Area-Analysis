'use client';

import { useEffect, useRef, useState } from 'react';
import { ChatMessage, AgentStep } from '@/lib/types';
import { useChatStore, type UserRole } from '@/stores/chatStore';
import MessageBubble from './MessageBubble';
import AgentProgressIndicator from './AgentProgressIndicator';
import { FeedbackRow } from '@/components/feedback';

interface MessageListProps {
  messages: ChatMessage[];
  isThinking: boolean;
  isLoading?: boolean;
  agentSteps?: AgentStep[];
  previewSlot?: React.ReactNode;
  /** C.1 — 빈 상태에서 role 별 추천 칩 클릭 시 호출. 미지정 시 칩 영역 숨김. */
  onSuggestionClick?: (suggestion: string) => void;
}

// C.1 — role 별 입문 질문 3개. role null 일 때는 default 사용.
const ROLE_STARTER_CHIPS: Record<UserRole, string[]> = {
  owner: ['이 자리 위험해?', '근처 비슷한 상권 비교', '주변 폐업률 알려줘'],
  investor: ['유망 상권 추천', '강남 vs 홍대 비교', '성장 중인 상권은?'],
  founder: ['카페 하면 어때?', '내 예산으로 가능한 업종', '명동 창업 추천 업종'],
};
const DEFAULT_STARTER_CHIPS = [
  '강남역 상권 요약',
  '홍대 vs 성수 비교',
  '카페 창업 추천 지역',
];

const ONBOARDING_STEPS: { num: number; title: string; desc: string }[] = [
  { num: 1, title: '지도에서 상권 선택', desc: '폴리곤을 클릭해 후보 지역을 고르세요' },
  { num: 2, title: '프리뷰로 빠른 요약', desc: '유동인구·주요 업종을 LLM 호출 없이 확인' },
  { num: 3, title: 'AI 분석 시작', desc: '질문 입력 또는 “AI 분석 보기”로 심층 분석' },
];

export default function MessageList({
  messages,
  isThinking,
  isLoading,
  agentSteps = [],
  previewSlot,
  onSuggestionClick,
}: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const role = useChatStore((s) => s.role);
  const starterChips = role ? ROLE_STARTER_CHIPS[role] : DEFAULT_STARTER_CHIPS;

  // IntersectionObserver 로 하단 sentinel 가시성 추적 →
  // 사용자가 위로 스크롤했는지 판정. 스트리밍 자동 스크롤은 하단일 때만.
  useEffect(() => {
    const sentinel = bottomRef.current;
    const root = containerRef.current;
    if (!sentinel || !root) return;
    const io = new IntersectionObserver(
      ([entry]) => setIsAtBottom(entry.isIntersecting),
      { root, threshold: 0, rootMargin: '0px 0px 100px 0px' },
    );
    io.observe(sentinel);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (isAtBottom) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isThinking, isAtBottom]);

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Find the last assistant text message index for streaming cursor
  let lastAssistantTextIdx = -1;
  if (isLoading) {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant' && messages[i].type !== 'card') {
        lastAssistantTextIdx = i;
        break;
      }
    }
  }

  const showEmpty = messages.length === 0 && !previewSlot;
  const showJumpFab = !isAtBottom && messages.length > 0;

  return (
    <div className="relative flex-1 overflow-hidden">
      <div
        ref={containerRef}
        className="absolute inset-0 overflow-y-auto px-4 py-4 space-y-4"
      >
        {previewSlot}
        {showEmpty && (
          <div
            data-testid="chat-empty-state"
            className="flex flex-col items-center justify-center h-full text-center px-4"
          >
            <div
              className="w-14 h-14 rounded-full flex items-center justify-center mb-3"
              style={{ backgroundColor: 'var(--bg-tertiary)' }}
            >
              <svg
                className="w-7 h-7 text-primary-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
              MarketScope AI
            </h3>
            <p className="text-xs mb-5" style={{ color: 'var(--text-muted)' }}>
              상권을 선택하고 AI에게 자유롭게 질문하세요.
            </p>

            {/* 3-step 진행 안내 */}
            <ol
              data-testid="chat-onboarding-steps"
              className="w-full max-w-xs space-y-2 mb-5 text-left"
            >
              {ONBOARDING_STEPS.map((step) => (
                <li
                  key={step.num}
                  className="flex items-start gap-2.5 px-3 py-2 rounded-lg"
                  style={{
                    backgroundColor: 'var(--bg-tertiary)',
                    border: '1px solid var(--border-color)',
                  }}
                >
                  <span
                    className="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-semibold"
                    style={{
                      backgroundColor: 'var(--bg-accent)',
                      color: '#fff',
                    }}
                  >
                    {step.num}
                  </span>
                  <span className="flex-1">
                    <span
                      className="block text-xs font-medium"
                      style={{ color: 'var(--text-primary)' }}
                    >
                      {step.title}
                    </span>
                    <span
                      className="block text-[11px] leading-tight mt-0.5"
                      style={{ color: 'var(--text-muted)' }}
                    >
                      {step.desc}
                    </span>
                  </span>
                </li>
              ))}
            </ol>

            {/* role 별 추천 칩 */}
            {onSuggestionClick && (
              <div
                data-testid="chat-empty-chips"
                data-role={role ?? 'default'}
                className="w-full max-w-xs"
              >
                <div
                  className="text-[11px] font-medium mb-2"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  이런 질문은 어떠세요?
                </div>
                <div className="flex flex-wrap justify-center gap-2">
                  {starterChips.map((q, idx) => (
                    <button
                      key={`${idx}-${q}`}
                      type="button"
                      data-testid={`chat-empty-chip-${idx}`}
                      onClick={() => onSuggestionClick(q)}
                      className="text-xs px-3 py-1.5 rounded-full transition-colors hover:opacity-80"
                      style={{
                        backgroundColor: 'var(--thinking-bg)',
                        color: 'var(--bg-accent)',
                        border: '1px solid var(--border-color)',
                      }}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {messages.map((message, idx) => (
          <MessageBubble
            key={message.id}
            message={message}
            isStreaming={idx === lastAssistantTextIdx}
          />
        ))}

        {!isLoading && messages.length > 0 && <FeedbackRow />}

        {agentSteps.length > 0 && <AgentProgressIndicator steps={agentSteps} />}

        {isThinking && agentSteps.length === 0 && (
          <div className="flex items-start gap-2">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0"
              style={{ backgroundColor: 'var(--bg-tertiary)' }}
            >
              <svg
                className="w-4 h-4 text-primary-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
            </div>
            <div
              className="rounded-2xl rounded-tl-sm px-4 py-2.5"
              style={{ backgroundColor: 'var(--bot-bubble)' }}
            >
              <div className="flex gap-1">
                <span
                  className="w-2 h-2 rounded-full animate-bounce"
                  style={{ backgroundColor: 'var(--text-muted)', animationDelay: '0ms' }}
                />
                <span
                  className="w-2 h-2 rounded-full animate-bounce"
                  style={{ backgroundColor: 'var(--text-muted)', animationDelay: '150ms' }}
                />
                <span
                  className="w-2 h-2 rounded-full animate-bounce"
                  style={{ backgroundColor: 'var(--text-muted)', animationDelay: '300ms' }}
                />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} aria-hidden="true" />
      </div>

      {showJumpFab && (
        <button
          type="button"
          data-testid="chat-jump-fab"
          onClick={scrollToBottom}
          aria-label="최신 메시지로 이동"
          className="absolute right-3 bottom-5 touch-target flex items-center gap-1 rounded-full px-3 text-sm font-medium transition-opacity hover:opacity-90"
          style={{
            backgroundColor: 'var(--bg-accent)',
            color: '#fff',
            paddingTop: 10,
            paddingBottom: 10,
            // C.2 — streaming 중에도 가시성 확보. 기본 shadow-lg 보다 짙게.
            boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
          }}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 14l-7 7m0 0l-7-7m7 7V3"
            />
          </svg>
          <span>최신 메시지</span>
        </button>
      )}
    </div>
  );
}
