'use client';

import Toolbar from '@/components/layout/Toolbar';
import MapContainer from '@/components/map/MapContainer';
import ChatPanel from '@/components/chat/ChatPanel';
import BottomSheet from './BottomSheet';
import BottomNav from './BottomNav';
import { useKeyboardInset } from '@/hooks/useKeyboardInset';

export default function MobileLayout() {
  useKeyboardInset();
  return (
    <div
      className="relative flex flex-col overflow-hidden"
      style={{ height: '100dvh' }}
      data-layout="mobile"
    >
      <Toolbar />
      <div className="relative flex-1 overflow-hidden">
        <MapContainer />
      </div>
      <BottomSheet>
        <ChatPanel />
      </BottomSheet>
      <BottomNav />
    </div>
  );
}
