'use client';

import { useEffect } from 'react';
import { X, AlertCircle, CheckCircle2, Info, AlertTriangle } from 'lucide-react';
import { useToastStore, type Toast as ToastModel, type ToastLevel } from '@/stores/toastStore';

const LEVEL_STYLES: Record<ToastLevel, { bg: string; fg: string; border: string }> = {
  info: { bg: 'rgba(11,61,145,0.95)', fg: '#ffffff', border: 'rgba(11,61,145,0.6)' },
  success: { bg: 'rgba(16,185,129,0.95)', fg: '#ffffff', border: 'rgba(16,185,129,0.6)' },
  warning: { bg: 'rgba(217,119,6,0.95)', fg: '#ffffff', border: 'rgba(217,119,6,0.6)' },
  error: { bg: 'rgba(220,38,38,0.95)', fg: '#ffffff', border: 'rgba(220,38,38,0.6)' },
};

function LevelIcon({ level }: { level: ToastLevel }) {
  const props = { size: 18, strokeWidth: 2, 'aria-hidden': true } as const;
  if (level === 'success') return <CheckCircle2 {...props} />;
  if (level === 'warning') return <AlertTriangle {...props} />;
  if (level === 'error') return <AlertCircle {...props} />;
  return <Info {...props} />;
}

function ToastItem({ toast }: { toast: ToastModel }) {
  const dismiss = useToastStore((s) => s.dismiss);
  const palette = LEVEL_STYLES[toast.level];

  useEffect(() => {
    const timer = window.setTimeout(() => dismiss(toast.id), toast.durationMs);
    return () => window.clearTimeout(timer);
  }, [toast.id, toast.durationMs, dismiss]);

  return (
    <div
      role={toast.level === 'error' ? 'alert' : 'status'}
      aria-live={toast.level === 'error' ? 'assertive' : 'polite'}
      data-testid="toast-item"
      data-toast-level={toast.level}
      className="flex items-start gap-3 px-4 py-3 rounded-xl shadow-lg max-w-sm pointer-events-auto"
      style={{
        backgroundColor: palette.bg,
        color: palette.fg,
        border: `1px solid ${palette.border}`,
      }}
    >
      <span className="mt-0.5 flex-shrink-0"><LevelIcon level={toast.level} /></span>
      <p className="flex-1 text-sm leading-snug" data-testid="toast-message">{toast.message}</p>
      {toast.actionLabel && toast.onAction ? (
        <button
          type="button"
          data-testid="toast-action"
          onClick={() => {
            toast.onAction?.();
            dismiss(toast.id);
          }}
          className="text-sm font-semibold underline-offset-2 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70 rounded"
          style={{ color: palette.fg }}
        >
          {toast.actionLabel}
        </button>
      ) : null}
      <button
        type="button"
        data-testid="toast-dismiss"
        aria-label="알림 닫기"
        onClick={() => dismiss(toast.id)}
        className="ml-1 flex-shrink-0 inline-flex items-center justify-center w-5 h-5 rounded hover:bg-white/15 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
      >
        <X size={14} strokeWidth={2} aria-hidden />
      </button>
    </div>
  );
}

export default function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);

  if (toasts.length === 0) return null;

  return (
    <div
      data-testid="toast-container"
      aria-label="알림"
      className="fixed z-[60] top-4 right-4 flex flex-col gap-2 pointer-events-none"
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  );
}
