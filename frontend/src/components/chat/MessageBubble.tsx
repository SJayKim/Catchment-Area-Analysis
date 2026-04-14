'use client';

import { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChatMessage } from '@/lib/types';
import { CARD_REGISTRY } from './cards/registry';

interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
}

function MessageBubble({ message, isStreaming }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isCard = message.type === 'card';
  const isError = message.type === 'error';

  // Card messages
  if (isCard && message.cardData) {
    return (
      <div className="flex items-start gap-2 animate-msg-in">
        <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0"
          style={{ backgroundColor: 'var(--bg-tertiary)' }}>
          <svg className="w-4 h-4 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>
        <div className="flex-1 max-w-[90%]">
          {(() => {
            const CardComponent = message.cardType ? CARD_REGISTRY[message.cardType] : undefined;
            if (CardComponent) {
              return <CardComponent data={message.cardData as any} />;
            }
            return (
              <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
                <pre className="text-xs whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
                  {JSON.stringify(message.cardData, null, 2)}
                </pre>
              </div>
            );
          })()}
        </div>
      </div>
    );
  }

  // User messages
  if (isUser) {
    return (
      <div className="flex justify-end animate-msg-in">
        <div className="max-w-[75%] text-white rounded-2xl rounded-tr-sm px-4 py-2.5"
          style={{ backgroundColor: 'var(--user-bubble)' }}>
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  // Assistant text / error messages
  return (
    <div className="flex items-start gap-2 animate-msg-in">
      <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0"
        style={{ backgroundColor: 'var(--bg-tertiary)' }}>
        <svg className="w-4 h-4 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>
      <div
        className={`max-w-[75%] rounded-2xl rounded-tl-sm px-4 py-2.5 ${isStreaming && !isError ? 'streaming' : ''}`}
        style={
          isError
            ? { backgroundColor: 'rgba(239,68,68,0.1)', border: '1px solid var(--error)' }
            : { backgroundColor: 'var(--bot-bubble)' }
        }
      >
        {isError ? (
          <p className="text-sm whitespace-pre-wrap" style={{ color: 'var(--error)' }}>
            {message.content || '\u200B'}
          </p>
        ) : (
          <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content || '\u200B'}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}

export default memo(MessageBubble, (prev, next) => {
  return (
    prev.message.id === next.message.id &&
    prev.message.content === next.message.content &&
    prev.isStreaming === next.isStreaming
  );
});
