"use client";

import { useState } from "react";

/**
 * Shows how an intent was resolved, next to the result it produced.
 *
 * The design goal is a status line, not a badge collection. An operator
 * scanning a page of results needs to notice the one that was resolved by a
 * model at low confidence — so that case gets the visual weight and the
 * ordinary regex case stays almost silent. Colour is backed by a text label
 * throughout, so the meaning survives greyscale and colour-blindness.
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

const SOURCE_COPY: Record<IntentSource, { label: string; detail: string }> = {
  regex: {
    label: "Pattern match",
    detail:
      "Matched a known command pattern locally. No model was called and nothing was sent off the server.",
  },
  llm: {
    label: "Language model",
    detail:
      "The pattern engine was unsure, so a language model proposed a tool call. The proposal was checked against the tool's schema before anything ran.",
  },
  cache: {
    label: "Cached result",
    detail:
      "This wording was resolved by a model earlier and reused from the local cache.",
  },
  none: {
    label: "Unresolved",
    detail: "The command could not be mapped to a tool, so nothing ran.",
  },
};

function band(confidence: number, source: IntentSource) {
  if (source === "none") return "none" as const;
  if (confidence >= 0.85) return "high" as const;
  if (confidence >= 0.65) return "medium" as const;
  return "low" as const;
}

const BAND_STYLES = {
  high: "text-emerald-700 dark:text-emerald-400",
  medium: "text-amber-700 dark:text-amber-400",
  low: "text-rose-700 dark:text-rose-400",
  none: "text-slate-500 dark:text-slate-400",
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
  const needsAttention = level === "low" || level === "none";

  return (
    <div className={`text-sm ${className}`}>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        {intent && (
          <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-800 dark:bg-slate-800 dark:text-slate-200">
            {intent}
          </code>
        )}

        <span className={`font-medium ${BAND_STYLES[level]}`}>
          {BAND_LABEL[level]}
          {source !== "none" && (
            <span className="ml-1 font-normal tabular-nums opacity-80">{pct}%</span>
          )}
        </span>

        <span className="text-slate-400 dark:text-slate-600" aria-hidden>
          /
        </span>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="rounded text-slate-600 underline decoration-dotted underline-offset-4 hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 dark:text-slate-400 dark:hover:text-slate-100"
        >
          {copy.label}
        </button>

        {typeof latencyMs === "number" && (
          <span className="tabular-nums text-xs text-slate-500 dark:text-slate-500">
            {latencyMs} ms
          </span>
        )}
        {typeof tokensUsed === "number" && tokensUsed > 0 && (
          <span className="tabular-nums text-xs text-slate-500 dark:text-slate-500">
            {tokensUsed.toLocaleString()} tokens
          </span>
        )}
      </div>

      {needsAttention && reason && (
        <p className="mt-1.5 border-l-2 border-current pl-2.5 text-slate-700 dark:text-slate-300">
          <span className={BAND_STYLES[level]}>{reason}</span>
        </p>
      )}

      {open && (
        <p className="mt-1.5 max-w-prose text-xs leading-relaxed text-slate-600 dark:text-slate-400">
          {copy.detail}
        </p>
      )}
    </div>
  );
}

export default IntentConfidence;
