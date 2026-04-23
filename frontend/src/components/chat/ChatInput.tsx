'use client';

import { useState, KeyboardEvent } from 'react';

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (!input.trim() || disabled) return;
    onSend(input.trim());
    setInput('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== 'Enter' || e.shiftKey) return;
    // 한글/일본어/중국어 IME 조합 중 Enter 는 조합 확정이므로 전송 금지.
    // `isComposing` 우선, `keyCode 229` 는 구 Chrome Android 보조 체크.
    if (e.nativeEvent.isComposing || e.keyCode === 229) return;
    e.preventDefault();
    handleSend();
  };

  return (
    <div
      className="flex-shrink-0"
      style={{
        padding: '0.75rem',
        paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))',
        borderTop: '1px solid var(--border-color)',
        // 모바일 가상 키보드가 올라오면 composer 가 가려지지 않도록 상방 여백
        marginBottom: 'var(--kb-inset, 0px)',
      }}
    >
      <div className="flex items-end gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="무엇이든 물어보세요..."
          rows={1}
          disabled={disabled}
          aria-label="메시지 입력"
          className="flex-1 resize-none rounded-xl px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:opacity-50"
          style={{
            backgroundColor: 'var(--bg-secondary)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border-color)',
            // WCAG: 본문/입력 최소 16px — iOS Safari 는 14px 이하에서 자동 zoom
            fontSize: '16px',
            lineHeight: 1.5,
          }}
        />
        <button
          onClick={handleSend}
          disabled={disabled || !input.trim()}
          aria-label="메시지 전송"
          className="touch-target w-11 h-11 md:w-10 md:h-10 text-white rounded-xl flex items-center justify-center hover:opacity-90 disabled:cursor-not-allowed transition-colors flex-shrink-0"
          style={{
            backgroundColor:
              disabled || !input.trim()
                ? 'var(--bg-tertiary)'
                : 'var(--bg-accent)',
          }}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
