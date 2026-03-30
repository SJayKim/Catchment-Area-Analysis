'use client';

import { useChat } from '@/hooks/useChat';
import MessageList from './MessageList';
import ChatInput from './ChatInput';
import SuggestionChips from './SuggestionChips';

export default function ChatPanel() {
  const { messages, isLoading, isThinking, suggestions, agentSteps, sendMessage } = useChat();

  return (
    <div className="flex flex-col h-full" style={{ backgroundColor: 'var(--bg-primary)' }}>
      {/* Header */}
      <div className="px-4 py-3 flex-shrink-0" style={{ borderBottom: '1px solid var(--border-color)' }}>
        <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>AI 상권 분석</h2>
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>상권에 대해 무엇이든 물어보세요</p>
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
