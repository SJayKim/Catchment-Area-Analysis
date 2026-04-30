import { create } from 'zustand';

export type ToastLevel = 'info' | 'success' | 'warning' | 'error';

export interface ToastOptions {
  actionLabel?: string;
  onAction?: () => void;
  durationMs?: number;
}

export interface Toast {
  id: string;
  message: string;
  level: ToastLevel;
  actionLabel?: string;
  onAction?: () => void;
  durationMs: number;
}

interface ToastState {
  toasts: Toast[];
  show: (message: string, level?: ToastLevel, options?: ToastOptions) => string;
  dismiss: (id: string) => void;
  clear: () => void;
}

const DEFAULT_DURATION_MS = 4000;
const ERROR_DURATION_MS = 7000;

function defaultDuration(level: ToastLevel): number {
  return level === 'error' ? ERROR_DURATION_MS : DEFAULT_DURATION_MS;
}

function generateId(): string {
  return `toast-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  show: (message, level = 'info', options = {}) => {
    const id = generateId();
    const toast: Toast = {
      id,
      message,
      level,
      actionLabel: options.actionLabel,
      onAction: options.onAction,
      durationMs: options.durationMs ?? defaultDuration(level),
    };
    set((s) => ({ toasts: [...s.toasts, toast] }));
    return id;
  },

  dismiss: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

  clear: () => set({ toasts: [] }),
}));

if (typeof window !== 'undefined') {
  (window as unknown as { __toastStore?: typeof useToastStore }).__toastStore =
    useToastStore;
}
