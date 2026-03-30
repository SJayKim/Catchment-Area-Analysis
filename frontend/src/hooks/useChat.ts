'use client';

import { useCallback } from 'react';
import { useChatStore } from '@/stores/chatStore';
import { useDistrictStore } from '@/stores/districtStore';
import { useMapStore } from '@/stores/mapStore';
import { SSEEvent } from '@/lib/types';

export function useChat() {
  const messages = useChatStore((s) => s.messages);
  const isLoading = useChatStore((s) => s.isLoading);
  const isThinking = useChatStore((s) => s.isThinking);
  const suggestions = useChatStore((s) => s.suggestions);
  const agentSteps = useChatStore((s) => s.agentSteps);

  const selected = useDistrictStore((s) => s.selected);
  const selectDistrict = useDistrictStore((s) => s.select);
  const setView = useMapStore((s) => s.setView);

  const sendMessage = useCallback(
    async (message: string) => {
      const onMapCmd = (event: SSEEvent) => {
        const action = event.action as string;
        if (action === 'move' && event.params) {
          const params = event.params as { lat: number; lng: number; zoom?: number };
          setView(
            { lat: params.lat, lng: params.lng },
            params.zoom || 5
          );
        }

        // Feature 3: Update districtStore from chat-originated map_cmd
        if (event.district_code && event.district_name) {
          selectDistrict(
            {
              code: event.district_code as string,
              name: event.district_name as string,
              type: (event.district_type as string) || '발달상권',
              center: event.params
                ? {
                    lat: (event.params as { lat: number; lng: number }).lat,
                    lng: (event.params as { lat: number; lng: number }).lng,
                  }
                : { lat: 0, lng: 0 },
            },
            'chat'
          );
        }
      };

      await useChatStore.getState().sendMessage(
        message,
        selected?.code,
        onMapCmd
      );
    },
    [selected?.code, setView, selectDistrict]
  );

  return {
    messages,
    isLoading,
    isThinking,
    suggestions,
    agentSteps,
    sendMessage,
  };
}
