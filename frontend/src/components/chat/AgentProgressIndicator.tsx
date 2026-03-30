'use client';

import { useState } from 'react';
import { AgentStep } from '@/lib/types';

interface AgentProgressIndicatorProps {
  steps: AgentStep[];
}

const STATUS_ICON: Record<string, string> = {
  pending: '⏳',
  in_progress: '⏳',
  completed: '✅',
};

export default function AgentProgressIndicator({ steps }: AgentProgressIndicatorProps) {
  const [collapsed, setCollapsed] = useState(false);

  if (steps.length === 0) return null;

  return (
    <div className="flex items-start gap-2 animate-msg-in">
      <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0"
        style={{ backgroundColor: 'var(--bg-tertiary)' }}>
        <svg className="w-4 h-4 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>
      <div className="rounded-2xl rounded-tl-sm px-4 py-2.5 min-w-[200px]"
        style={{ backgroundColor: 'var(--thinking-bg)', border: '1px solid var(--thinking-border)' }}>
        {/* Header with toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-1.5 text-xs font-medium mb-1 w-full text-left"
          style={{ color: 'var(--text-secondary)' }}
        >
          <span>{collapsed ? '▶' : '▼'}</span>
          <span>분석 진행</span>
        </button>

        {/* Steps list */}
        {!collapsed && (
          <div className="space-y-1">
            {steps.map((step, idx) => (
              <div
                key={step.id}
                className="flex items-center gap-2 text-sm transition-opacity duration-300 animate-step-in"
                style={{
                  color: step.status === 'completed'
                    ? 'var(--text-muted)'
                    : step.status === 'in_progress'
                      ? 'var(--text-primary)'
                      : 'var(--text-muted)',
                  fontWeight: step.status === 'in_progress' ? 500 : 400,
                  animationDelay: `${idx * 50}ms`,
                }}
              >
                <span className="text-xs leading-none">{STATUS_ICON[step.status]}</span>
                <span>{step.label}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
