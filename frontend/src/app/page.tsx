'use client';

import Toolbar from '@/components/layout/Toolbar';
import SplitPanel from '@/components/layout/SplitPanel';
import StatusBar from '@/components/layout/StatusBar';
import MapContainer from '@/components/map/MapContainer';
import ChatPanel from '@/components/chat/ChatPanel';
import { useMapSync } from '@/hooks/useMapSync';

export default function Home() {
  useMapSync();

  return (
    <div className="flex flex-col h-screen">
      <Toolbar />
      <SplitPanel
        left={<MapContainer />}
        right={<ChatPanel />}
      />
      <StatusBar />
    </div>
  );
}
