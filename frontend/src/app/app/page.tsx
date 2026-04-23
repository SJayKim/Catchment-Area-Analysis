'use client';

import { Suspense, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import Toolbar from '@/components/layout/Toolbar';
import SplitPanel from '@/components/layout/SplitPanel';
import StatusBar from '@/components/layout/StatusBar';
import MapContainer from '@/components/map/MapContainer';
import ChatPanel from '@/components/chat/ChatPanel';
import MobileLayout from '@/components/mobile/MobileLayout';
import { FeedbackFab, FreeLimitSurvey } from '@/components/feedback';
import { useChatStore } from '@/stores/chatStore';
import { useMapSync } from '@/hooks/useMapSync';
import { useBreakpoint } from '@/hooks/useBreakpoint';

const DAILY_FREE_LIMIT = 5;

type Role = 'owner' | 'investor' | 'founder';
const VALID_ROLES: Role[] = ['owner', 'investor', 'founder'];

function DeepLinkHandler() {
  const searchParams = useSearchParams();

  useEffect(() => {
    // Role — URL param first, fall back to localStorage on repeat visits
    const rawRole = searchParams?.get('role');
    let role: Role | null = null;
    if (rawRole && (VALID_ROLES as string[]).includes(rawRole)) {
      role = rawRole as Role;
      try {
        window.localStorage.setItem('ms_role', role);
      } catch {
        // localStorage may be unavailable — ignore
      }
    } else {
      try {
        const stored = window.localStorage.getItem('ms_role');
        if (stored && (VALID_ROLES as string[]).includes(stored)) {
          role = stored as Role;
        }
      } catch {
        // ignore
      }
    }
    useChatStore.getState().setRole(role);

    const q = searchParams?.get('q');
    if (q && q.trim()) {
      const MAX_LEN = 500;
      const prompt = q.slice(0, MAX_LEN).trim();
      const timer = window.setTimeout(() => {
        useChatStore.getState().sendMessage(prompt);
      }, 300);
      return () => window.clearTimeout(timer);
    }
  }, [searchParams]);

  return null;
}

function AppContent() {
  useMapSync();
  const messageCount = useChatStore((s) => s.messageCount);
  const bp = useBreakpoint();

  if (bp === 'mobile') {
    return (
      <div data-breakpoint={bp}>
        <Suspense fallback={null}>
          <DeepLinkHandler />
        </Suspense>
        <MobileLayout />
        <FeedbackFab />
        <FreeLimitSurvey trigger={messageCount >= DAILY_FREE_LIMIT} />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen" data-breakpoint={bp}>
      <Suspense fallback={null}>
        <DeepLinkHandler />
      </Suspense>
      <Toolbar />
      <SplitPanel
        left={<MapContainer />}
        right={<ChatPanel />}
      />
      <StatusBar />
      <FeedbackFab />
      <FreeLimitSurvey trigger={messageCount >= DAILY_FREE_LIMIT} />
    </div>
  );
}

export default function AppPage() {
  return (
    <Suspense fallback={null}>
      <AppContent />
    </Suspense>
  );
}
