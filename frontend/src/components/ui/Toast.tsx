"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { CheckCircle2, XCircle, Info, AlertTriangle, ShieldX, X } from "lucide-react";

export type ToastVariant = "success" | "error" | "info" | "warn" | "denied";

export interface Toast {
  id: number;
  message: string;
  variant: ToastVariant;
  ttl: number;
}

interface Ctx {
  push: (msg: string, variant?: ToastVariant, ttl?: number) => void;
}

const ToastContext = createContext<Ctx | null>(null);

export function useToast(): Ctx {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // Safe no-op fallback so components don't crash if provider missing
    return { push: () => {} };
  }
  return ctx;
}

let _id = 1;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const remove = useCallback((id: number) => {
    setToasts((list) => list.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (message: string, variant: ToastVariant = "info", ttl = 4000) => {
      const t: Toast = { id: _id++, message, variant, ttl };
      setToasts((list) => [...list, t]);
    },
    []
  );

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div
        className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 max-w-sm w-[calc(100vw-2rem)]"
        aria-live="polite"
      >
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={() => remove(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  useEffect(() => {
    const tm = setTimeout(onDismiss, toast.ttl);
    return () => clearTimeout(tm);
  }, [toast.ttl, onDismiss]);

  const styles: Record<ToastVariant, { ring: string; icon: React.ElementType; color: string }> = {
    success: {
      ring: "ring-emerald-600/20 bg-emerald-50 text-emerald-900 dark:ring-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-200",
      icon: CheckCircle2,
      color: "tone-success",
    },
    error: {
      ring: "ring-red-600/20 bg-red-50 text-red-900 dark:ring-red-400/20 dark:bg-red-500/10 dark:text-red-200",
      icon: XCircle,
      color: "tone-failed",
    },
    denied: {
      ring: "ring-blue-600/20 bg-blue-50 text-blue-900 dark:ring-blue-400/20 dark:bg-blue-500/10 dark:text-blue-200",
      icon: ShieldX,
      color: "tone-denied",
    },
    warn: {
      ring: "ring-amber-600/20 bg-amber-50 text-amber-900 dark:ring-amber-400/20 dark:bg-amber-500/10 dark:text-amber-200",
      icon: AlertTriangle,
      color: "tone-pending",
    },
    info: {
      ring: "ring-zinc-300 bg-white text-zinc-900 dark:ring-zinc-700 dark:bg-zinc-900 dark:text-zinc-100",
      icon: Info,
      color: "text-zinc-500 dark:text-zinc-400",
    },
  };
  const s = styles[toast.variant];
  const Icon = s.icon;

  return (
    <div className={"flex items-start gap-2 rounded-lg p-3 pr-2 ring-1 " + s.ring}>
      <Icon className={"h-4 w-4 mt-0.5 shrink-0 " + s.color} />
      <p className="text-sm flex-1 break-words">{toast.message}</p>
      <button
        type="button"
        onClick={onDismiss}
        className="p-1 rounded hover:bg-black/5 dark:hover:bg-white/10 shrink-0"
        aria-label="Dismiss"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
