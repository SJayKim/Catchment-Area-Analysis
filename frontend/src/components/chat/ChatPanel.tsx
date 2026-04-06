'use client';

import { useEffect } from 'react';
import { useChat } from '@/hooks/useChat';
import { useReportExport } from '@/hooks/useReportExport';
import { useDistrictStore } from '@/stores/districtStore';
import MessageList from './MessageList';
import ChatInput from './ChatInput';
import SuggestionChips from './SuggestionChips';

export default function ChatPanel() {
  const { messages, isLoading, isThinking, suggestions, agentSteps, sendMessage } = useChat();
  const selected = useDistrictStore((s) => s.selected);

  const { generatePDF, isGenerating } = useReportExport({
    districtName: selected?.name || '',
    dataQuarter: selected?.dataQuarter || '',
    messages,
  });

  const hasContent = messages.length > 0;

  // Listen for chat-triggered PDF generation
  useEffect(() => {
    const handler = () => { generatePDF(); };
    window.addEventListener('marketscope:generate-pdf', handler);
    return () => window.removeEventListener('marketscope:generate-pdf', handler);
  }, [generatePDF]);

  return (
    <div className="flex flex-col h-full" style={{ backgroundColor: 'var(--bg-primary)' }}>
      {/* Header */}
      <div className="px-4 py-3 flex-shrink-0 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border-color)' }}>
        <div>
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>AI 상권 분석</h2>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>상권에 대해 무엇이든 물어보세요</p>
        </div>
        {hasContent && (
          <button
            onClick={generatePDF}
            disabled={isGenerating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
            style={{
              backgroundColor: isGenerating ? 'var(--bg-tertiary)' : 'rgba(59,130,246,0.1)',
              color: isGenerating ? 'var(--text-muted)' : '#3b82f6',
              border: '1px solid rgba(59,130,246,0.2)',
            }}
            title="PDF 리포트 내보내기"
          >
            {isGenerating ? (
              <>
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                생성 중...
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                PDF
              </>
            )}
          </button>
        )}
      </div>

      {/* Messages */}
      <MessageList messages={messages} isThinking={isThinking} isLoading={isLoading} agentSteps={agentSteps} />

      {/* Suggestions */}
      <SuggestionChips
        suggestions={suggestions}
        onSelect={sendMessage}
        disabled={isLoading}
      />

      {/* Input */}
      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </div>
  );
}
