'use client';

import { useEffect, useRef } from 'react';
import { ChatMessage, AgentStep } from '@/lib/types';
import MessageBubble from './MessageBubble';
import AgentProgressIndicator from './AgentProgressIndicator';

interface MessageListProps {
  messages: ChatMessage[];
  isThinking: boolean;
  isLoading?: boolean;
  agentSteps?: AgentStep[];
}

export default function MessageList({ messages, isThinking, isLoading, agentSteps = [] }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

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

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
      {messages.length === 0 && (
        <div className="flex flex-col items-center justify-center h-full text-center">
          <div className="w-16 h-16 rounded-full flex items-center justify-center mb-4"
            style={{ backgroundColor: 'var(--bg-tertiary)' }}>
            <svg className="w-8 h-8 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
          </div>
          <h3 className="text-lg font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
            MarketScope AI
          </h3>
          <p className="text-sm max-w-xs" style={{ color: 'var(--text-muted)' }}>
            지도에서 상권을 선택하거나, 아래 질문을 눌러 분석을 시작하세요.
          </p>
        </div>
      )}

      {messages.map((message, idx) => (
        <MessageBubble
          key={message.id}
          message={message}
          isStreaming={idx === lastAssistantTextIdx}
        />
      ))}

      {agentSteps.length > 0 && (
        <AgentProgressIndicator steps={agentSteps} />
      )}

      {isThinking && agentSteps.length === 0 && (
        <div className="flex items-start gap-2">
          <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0"
            style={{ backgroundColor: 'var(--bg-tertiary)' }}>
            <svg className="w-4 h-4 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <div className="rounded-2xl rounded-tl-sm px-4 py-2.5" style={{ backgroundColor: 'var(--bot-bubble)' }}>
            <div className="flex gap-1">
              <span className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: 'var(--text-muted)', animationDelay: '0ms' }} />
              <span className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: 'var(--text-muted)', animationDelay: '150ms' }} />
              <span className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: 'var(--text-muted)', animationDelay: '300ms' }} />
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
