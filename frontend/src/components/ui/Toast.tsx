"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { CheckCircle2, XCircle, Info, AlertTriangle, X } from "lucide-react";

export type ToastVariant = "success" | "error" | "info" | "warn";

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
      ring: "ring-emerald-200 bg-emerald-50 text-emerald-900 dark:ring-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200",
      icon: CheckCircle2,
      color: "text-emerald-600 dark:text-emerald-400",
    },
    error: {
      ring: "ring-red-200 bg-red-50 text-red-900 dark:ring-red-500/30 dark:bg-red-500/10 dark:text-red-200",
      icon: XCircle,
      color: "text-red-600 dark:text-red-400",
    },
    warn: {
      ring: "ring-amber-200 bg-amber-50 text-amber-900 dark:ring-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200",
      icon: AlertTriangle,
      color: "text-amber-600 dark:text-amber-400",
    },
    info: {
      ring: "ring-brand-200 bg-brand-50 text-brand-900 dark:ring-brand-500/30 dark:bg-brand-500/10 dark:text-brand-200",
      icon: Info,
      color: "text-brand-600 dark:text-brand-400",
    },
  };
  const s = styles[toast.variant];
  const Icon = s.icon;

  return (
    <div
      className={
        "flex items-start gap-2 rounded-xl p-3 pr-2 ring-1 shadow-lg backdrop-blur " +
        s.ring
      }
    >
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
