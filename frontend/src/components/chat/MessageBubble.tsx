'use client';

import { ChatMessage } from '@/lib/types';
import SummaryCard from './cards/SummaryCard';
import CompareCard from './cards/CompareCard';
import RecommendCard from './cards/RecommendCard';
import RiskCard from './cards/RiskCard';

interface MessageBubbleProps {
  message: ChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isCard = message.type === 'card';
  const isError = message.type === 'error';

  // Card messages
  if (isCard && message.cardData) {
    return (
      <div className="flex items-start gap-2">
        <div className="w-7 h-7 bg-primary-100 rounded-full flex items-center justify-center flex-shrink-0">
          <svg className="w-4 h-4 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>
        <div className="flex-1 max-w-[90%]">
          {message.cardType === 'summary' ? (
            <SummaryCard data={message.cardData as any} />
          ) : message.cardType === 'compare' ? (
            <CompareCard data={message.cardData as any} />
          ) : message.cardType === 'recommend' ? (
            <RecommendCard data={message.cardData as any} />
          ) : message.cardType === 'risk' ? (
            <RiskCard data={message.cardData as any} />
          ) : (
            <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
              <pre className="text-xs text-gray-600 whitespace-pre-wrap">
                {JSON.stringify(message.cardData, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    );
  }

  // User messages
  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] bg-primary-500 text-white rounded-2xl rounded-tr-sm px-4 py-2.5">
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  // Assistant text / error messages
  return (
    <div className="flex items-start gap-2">
      <div className="w-7 h-7 bg-primary-100 rounded-full flex items-center justify-center flex-shrink-0">
        <svg className="w-4 h-4 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>
      <div
        className={`max-w-[75%] rounded-2xl rounded-tl-sm px-4 py-2.5 ${
          isError
            ? 'bg-red-50 border border-red-200'
            : 'bg-gray-100'
        }`}
      >
        <p
          className={`text-sm whitespace-pre-wrap ${
            isError ? 'text-red-600' : 'text-gray-800'
          }`}
        >
          {message.content || '\u200B'}
        </p>
      </div>
    </div>
  );
}
