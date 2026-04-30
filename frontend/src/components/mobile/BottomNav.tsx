'use client';

import { useChatStore, type MobileTab } from '@/stores/chatStore';

type TabDef = { id: MobileTab; label: string; icon: string };
const TABS: TabDef[] = [
  { id: 'map', label: '지도', icon: '🗺️' },
  { id: 'chat', label: '챗', icon: '💬' },
];

export default function BottomNav() {
  const active = useChatStore((s) => s.mobileTab);
  const setTab = useChatStore((s) => s.setMobileTab);
  const setSnap = useChatStore((s) => s.setSheetSnap);
  const unread = useChatStore((s) => s.unreadCount);

  const onSelect = (id: MobileTab) => {
    setTab(id);
    setSnap(id === 'chat' ? 'full' : 'peek');
  };

  return (
    <nav
      role="tablist"
      aria-label="모바일 주요 탭"
      className="fixed left-0 right-0 bottom-0 z-40 flex items-stretch border-t"
      style={{
        backgroundColor: 'var(--bg-primary)',
        borderTopColor: 'var(--border-color)',
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}
    >
      {TABS.map((tab) => {
        const selected = active === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-label={tab.label}
            className="relative flex-1 flex flex-col items-center justify-center touch-target"
            style={{
              minHeight: 60,
              color: selected ? 'var(--brand-deep-blue)' : 'var(--text-muted)',
              fontWeight: selected ? 600 : 400,
            }}
            onClick={() => onSelect(tab.id)}
          >
            <span aria-hidden="true" className="text-[24px] leading-none">
              {tab.icon}
            </span>
            <span className="mt-0.5 text-[13px] leading-none">{tab.label}</span>
            {tab.id === 'chat' && unread > 0 && (
              <span
                aria-label={`새 메시지 ${unread}개`}
                className="absolute top-1 right-[30%] flex items-center justify-center rounded-full text-[10px] font-semibold text-white"
                style={{
                  minWidth: 16,
                  height: 16,
                  padding: '0 4px',
                  backgroundColor: 'var(--error)',
                }}
              >
                {unread > 9 ? '9+' : unread}
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );
}
