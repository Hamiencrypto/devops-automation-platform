"use client";

import { useState } from "react";
import { Cpu, Regex, Database, HelpCircle } from "lucide-react";

/**
 * Shows how an intent was resolved, next to the result it produced.
 *
 * The design goal is a status line, not a badge collection. An operator
 * scanning a page of results needs to notice the one that was resolved by a
 * model at low confidence — so that case gets the visual weight (the
 * reserved "degraded confidence" violet) and the ordinary regex case stays
 * almost silent. Colour is backed by an icon and a text label throughout,
 * so the meaning survives greyscale and colour-blindness.
 */

export type IntentSource = "regex" | "llm" | "cache" | "none";

export interface IntentConfidenceProps {
  confidence: number; // 0..1
  source: IntentSource;
  intent?: string | null;
  reason?: string;
  tokensUsed?: number;
  latencyMs?: number;
  className?: string;
}

const SOURCE_COPY: Record<IntentSource, { label: string; detail: string; icon: typeof Regex }> = {
  regex: {
    label: "Pattern match",
    icon: Regex,
    detail:
      "Matched a known command pattern locally. No model was called and nothing was sent off the server.",
  },
  llm: {
    label: "Language model",
    icon: Cpu,
    detail:
      "The pattern engine was unsure, so a language model proposed a tool call. The proposal was checked against the tool's schema before anything ran.",
  },
  cache: {
    label: "Cached resolution",
    icon: Database,
    detail:
      "This wording was resolved by a model earlier and reused from the local cache.",
  },
  none: {
    label: "Unresolved",
    icon: HelpCircle,
    detail: "The command could not be mapped to a tool, so nothing ran.",
  },
};

function band(confidence: number, source: IntentSource) {
  if (source === "none") return "none" as const;
  if (confidence >= 0.85) return "high" as const;
  if (confidence >= 0.65) return "medium" as const;
  return "low" as const;
}

// Only "degraded" (low/none) is one of the five reserved meaning colours.
// High/medium confidence is deliberately unremarkable — the point is that
// the one case worth noticing is the one that stands out.
const BAND_STYLES = {
  high: "text-zinc-700 dark:text-zinc-300",
  medium: "text-zinc-700 dark:text-zinc-300",
  low: "tone-degraded font-semibold",
  none: "tone-degraded font-semibold",
} as const;

const BAND_LABEL = {
  high: "High confidence",
  medium: "Moderate confidence",
  low: "Low confidence",
  none: "No match",
} as const;

export function IntentConfidence({
  confidence,
  source,
  intent,
  reason,
  tokensUsed,
  latencyMs,
  className = "",
}: IntentConfidenceProps) {
  const [open, setOpen] = useState(false);
  const level = band(confidence, source);
  const pct = Math.round(Math.max(0, Math.min(1, confidence)) * 100);
  const copy = SOURCE_COPY[source];
  const SourceIcon = copy.icon;
  const needsAttention = level === "low" || level === "none";

  return (
    <div className={`text-sm ${className}`}>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        {intent && (
          <code className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-xs text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200">
            {intent}
          </code>
        )}

        <span className={`font-medium ${BAND_STYLES[level]}`}>
          {BAND_LABEL[level]}
          {source !== "none" && (
            <span className="ml-1 font-normal tabular-nums opacity-80">{pct}%</span>
          )}
        </span>

        <span className="text-zinc-300 dark:text-zinc-700" aria-hidden>
          /
        </span>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="inline-flex items-center gap-1 rounded text-zinc-600 underline decoration-dotted underline-offset-4 hover:text-zinc-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          <SourceIcon className="h-3 w-3" />
          {copy.label}
        </button>

        {typeof latencyMs === "number" && (
          <span className="tabular-nums text-xs text-zinc-500 dark:text-zinc-500">
            {latencyMs}ms
          </span>
        )}
        {typeof tokensUsed === "number" && tokensUsed > 0 && (
          <span className="tabular-nums text-xs text-zinc-500 dark:text-zinc-500">
            {tokensUsed.toLocaleString()} tok
          </span>
        )}
      </div>

      {needsAttention && reason && (
        <p className="mt-1.5 border-l-2 border-current pl-2.5 tone-degraded">
          {reason}
        </p>
      )}

      {open && (
        <p className="mt-1.5 max-w-prose text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
          {copy.detail}
        </p>
      )}
    </div>
  );
}

export default IntentConfidence;
