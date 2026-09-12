/**
 * Single source of truth for how a TaskStatus is presented.
 *
 * This used to be three separate colour maps (ResultsDisplay, TaskHistory,
 * history/page.tsx), each drifting slightly — "blocked" and "failed" ended
 * up close enough in colour that they read alike at a glance, which is
 * exactly the distinction the interface is supposed to make legible. One
 * map, imported everywhere a status renders.
 *
 * `requireConfirmation` only ever comes from a live ExecuteResponse — the
 * task-history list (TaskOut) doesn't carry that field, so a historical
 * blocked task always reads as "Denied by policy" rather than the
 * confirmation sub-state, which only exists for the response you just got
 * back from /execute.
 */

import {
  CheckCircle2,
  ShieldAlert,
  ShieldX,
  XCircle,
  Loader2,
  Clock,
  FlaskConical,
  type LucideIcon,
} from "lucide-react";
import type { TaskStatus } from "@/lib/api";

export type StatusTone = "success" | "denied" | "pending" | "failed" | "neutral";

export interface StatusMeta {
  tone: StatusTone;
  label: string;
  icon: LucideIcon;
  /** Text colour class, e.g. for an icon or inline label. */
  textClass: string;
  /** Full pill/badge treatment. */
  badgeClass: string;
}

const META: Record<StatusTone, Omit<StatusMeta, "label" | "icon">> = {
  success: { tone: "success", textClass: "tone-success", badgeClass: "badge-success" },
  denied: { tone: "denied", textClass: "tone-denied", badgeClass: "badge-denied" },
  pending: { tone: "pending", textClass: "tone-pending", badgeClass: "badge-pending" },
  failed: { tone: "failed", textClass: "tone-failed", badgeClass: "badge-failed" },
  neutral: { tone: "neutral", textClass: "tone-neutral", badgeClass: "badge-neutral" },
};

export function getStatusMeta(
  status: TaskStatus,
  requireConfirmation = false
): StatusMeta {
  switch (status) {
    case "success":
      return { ...META.success, label: "Succeeded", icon: CheckCircle2 };
    case "dry_run":
      return { ...META.success, label: "Dry run", icon: FlaskConical };
    case "blocked":
      return requireConfirmation
        ? { ...META.pending, label: "Needs confirmation", icon: ShieldAlert }
        : { ...META.denied, label: "Denied by policy", icon: ShieldX };
    case "failed":
      return { ...META.failed, label: "Failed", icon: XCircle };
    case "running":
      return { ...META.neutral, label: "Running", icon: Loader2 };
    case "pending":
    default:
      return { ...META.neutral, label: "Pending", icon: Clock };
  }
}
