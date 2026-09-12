"use client";

import { useEffect, useRef } from "react";
import { ShieldAlert, AlertTriangle, Info, X, Loader2 } from "lucide-react";

export type ConfirmIntent = "danger" | "warn" | "info";

interface Props {
  open: boolean;
  title: string;
  message: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  intent?: ConfirmIntent;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const INTENT_STYLE: Record<ConfirmIntent, { icon: typeof ShieldAlert; iconClass: string; btn: string }> = {
  danger: {
    icon: AlertTriangle,
    iconClass: "tone-failed bg-red-50 dark:bg-red-500/10",
    btn: "btn-danger",
  },
  warn: {
    icon: ShieldAlert,
    iconClass: "tone-pending bg-amber-50 dark:bg-amber-500/10",
    btn: "btn bg-amber-600 text-white hover:bg-amber-700 focus-visible:ring-amber-500",
  },
  info: {
    icon: Info,
    iconClass: "text-zinc-600 dark:text-zinc-300 bg-zinc-100 dark:bg-zinc-800",
    btn: "btn-primary",
  },
};

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  intent = "danger",
  busy = false,
  onConfirm,
  onCancel,
}: Props) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onCancel();
    };
    document.addEventListener("keydown", onKey);
    confirmRef.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open, busy, onCancel]);

  if (!open) return null;

  const style = INTENT_STYLE[intent];
  const Icon = style.icon;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-zinc-950/40"
      onClick={() => !busy && onCancel()}
      role="presentation"
    >
      <div
        className="card w-full max-w-md p-5"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
      >
        <div className="flex items-start gap-3">
          <div className={"h-9 w-9 rounded-full flex items-center justify-center shrink-0 " + style.iconClass}>
            <Icon className="h-4.5 w-4.5" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 id="confirm-dialog-title" className="font-semibold heading text-sm">
              {title}
            </h3>
            <div className="text-sm muted mt-1">{message}</div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="btn-ghost p-1 -mr-1 -mt-1"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-5 flex items-center justify-end gap-2">
          <button type="button" onClick={onCancel} disabled={busy} className="btn-secondary">
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={style.btn}
          >
            {busy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Working…
              </>
            ) : (
              confirmLabel
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
