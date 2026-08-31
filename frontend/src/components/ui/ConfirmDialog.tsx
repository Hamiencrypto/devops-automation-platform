"use client";

import { useEffect } from "react";
import { AlertTriangle, X, Loader2 } from "lucide-react";

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
  // Close on escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, busy, onCancel]);

  if (!open) return null;

  const btnClass =
    intent === "danger"
      ? "btn-danger"
      : intent === "warn"
        ? "btn-primary bg-amber-500 hover:bg-amber-600 focus:ring-amber-400"
        : "btn-primary";

  const iconClass =
    intent === "danger"
      ? "bg-red-100 text-red-600 dark:bg-red-500/15 dark:text-red-300"
      : intent === "warn"
        ? "bg-amber-100 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300"
        : "bg-brand-100 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4
                 bg-slate-900/50 backdrop-blur-sm"
      onClick={() => !busy && onCancel()}
    >
      <div
        className="card w-full max-w-md p-6 animate-in fade-in zoom-in duration-150"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-start gap-3">
          <div
            className={
              "h-10 w-10 rounded-full flex items-center justify-center shrink-0 " +
              iconClass
            }
          >
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold heading text-base">{title}</h3>
            <div className="text-sm muted mt-1">{message}</div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="btn-ghost p-1.5 -mr-1 -mt-1"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-6 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="btn-secondary"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={btnClass}
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
