'use client';

import { useCallback } from 'react';
import { useChatStore } from '@/stores/chatStore';
import { useDistrictStore } from '@/stores/districtStore';
import { useMapStore } from '@/stores/mapStore';
import { sendChatMessage } from '@/lib/api';
import { ChatMessage, SSEEvent } from '@/lib/types';

function generateId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function useChat() {
  const {
    messages,
    isLoading,
    isThinking,
    sessionId,
    suggestions,
    addMessage,
    updateLastAssistantMessage,
    setLoading,
    setThinking,
    setSuggestions,
  } = useChatStore();

  const selected = useDistrictStore((s) => s.selected);
  const setView = useMapStore((s) => s.setView);

  const sendMessage = useCallback(
    async (message: string) => {
      if (!message.trim() || isLoading) return;

      const userMessage: ChatMessage = {
        id: generateId(),
        role: 'user',
        content: message.trim(),
        type: 'text',
        timestamp: new Date(),
      };
      addMessage(userMessage);
      setLoading(true);
      setThinking(true);

      const assistantMessage: ChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: '',
        type: 'text',
        timestamp: new Date(),
      };
      addMessage(assistantMessage);

      try {
        const response = await sendChatMessage(
          message.trim(),
          sessionId,
          selected?.code
        );

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('No response body');
        }

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
              handleSSEEvent(event);
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
              handleSSEEvent(event);
            } catch {
              // Skip malformed JSON
            }
          }
        }
      } catch (error) {
        const errorMessage: ChatMessage = {
          id: generateId(),
          role: 'assistant',
          content: '죄송합니다. 요청을 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
          type: 'error',
          timestamp: new Date(),
        };
        addMessage(errorMessage);
      } finally {
        setLoading(false);
        setThinking(false);
      }
    },
    [
      isLoading,
      sessionId,
      selected,
      addMessage,
      updateLastAssistantMessage,
      setLoading,
      setThinking,
      setSuggestions,
      setView,
    ]
  );

  function handleSSEEvent(event: SSEEvent) {
    switch (event.type) {
      case 'thinking':
        setThinking(true);
        break;

      case 'text':
        setThinking(false);
        updateLastAssistantMessage(event.content as string);
        break;

      case 'card': {
        const cardMessage: ChatMessage = {
          id: generateId(),
          role: 'assistant',
          content: '',
          type: 'card',
          cardType: event.card_type as string,
          cardData: event.data as Record<string, unknown>,
          timestamp: new Date(),
        };
        addMessage(cardMessage);
        break;
      }

      case 'map_cmd': {
        const action = event.action as string;
        if (action === 'move' && event.params) {
          const params = event.params as { lat: number; lng: number; zoom?: number };
          setView(
            { lat: params.lat, lng: params.lng },
            params.zoom || 5
          );
        }
        break;
      }

      case 'suggestion':
        setSuggestions(event.questions as string[]);
        break;

      case 'done':
        setLoading(false);
        setThinking(false);
        break;

      case 'error':
        setThinking(false);
        updateLastAssistantMessage(
          (event.message as string) || '오류가 발생했습니다.'
        );
        break;

      case 'tool':
        // Tool call indicator - keep thinking state
        break;
    }
  }

  return {
    messages,
    isLoading,
    isThinking,
    suggestions,
    sendMessage,
  };
}
