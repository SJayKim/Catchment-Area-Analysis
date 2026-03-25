'use client';

import { useChat } from '@/hooks/useChat';
import MessageList from './MessageList';
import ChatInput from './ChatInput';
import SuggestionChips from './SuggestionChips';

export default function ChatPanel() {
  const { messages, isLoading, isThinking, suggestions, sendMessage } = useChat();

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 flex-shrink-0">
        <h2 className="text-sm font-semibold text-gray-800">AI 상권 분석</h2>
        <p className="text-xs text-gray-400">상권에 대해 무엇이든 물어보세요</p>
      </div>

      {/* Messages */}
      <MessageList messages={messages} isThinking={isThinking} />

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
