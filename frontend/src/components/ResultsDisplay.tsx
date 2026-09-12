"use client";

import { AlertTriangle } from "lucide-react";
import type { ExecuteResponse } from "@/lib/api";
import { IntentConfidence } from "@/components/IntentConfidence";
import { getStatusMeta } from "@/lib/status";

interface Props {
  response: ExecuteResponse | null;
}

export default function ResultsDisplay({ response }: Props) {
  if (!response) return null;

  const meta = getStatusMeta(response.status, response.require_confirmation);
  const StatusIcon = meta.icon;
  const isDenial = response.status === "blocked";
  const isFailure = response.status === "failed";

  return (
    <div className="card p-4 space-y-3.5">
      {/* Header — outcome first, always */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-2.5">
          <StatusIcon className={"h-5 w-5 mt-0.5 shrink-0 " + meta.textClass} />
          <div>
            <div className="flex items-center gap-2">
              <h2 className={"text-sm font-semibold " + meta.textClass}>{meta.label}</h2>
              <span className="text-xs text-zinc-400 dark:text-zinc-600 font-mono tabular-nums">
                #{response.task_id}
              </span>
            </div>
            {!isDenial && (
              <p className="text-sm muted mt-0.5">
                {response.summary || response.error || "No summary"}
              </p>
            )}
          </div>
        </div>
        {typeof response.duration_ms === "number" && (
          <span className="text-xs tabular-nums muted shrink-0">
            {response.duration_ms}ms
          </span>
        )}
      </div>

      {/* Denial / confirmation — the safety boundary speaking, not an error */}
      {isDenial && (
        <div className={"rounded-md border-l-2 border-current pl-3 py-1.5 text-sm " + meta.textClass}>
          {response.error}
          {response.require_confirmation && (
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
              Confirm in the dialog to proceed, or change the command.
            </p>
          )}
        </div>
      )}

      {/* Failure — the one state that should read as broken */}
      {isFailure && response.error && (
        <div className="rounded-md border-l-2 border-current tone-failed pl-3 py-1.5 text-sm">
          {response.error}
        </div>
      )}

      {response.intent && (
        <>
          <IntentConfidence
            intent={response.intent.intent}
            confidence={response.intent.confidence}
            source={response.intent.source}
            reason={response.intent.matched_pattern ?? undefined}
            tokensUsed={response.intent.tokens_used}
            latencyMs={response.intent.latency_ms}
          />

          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <dt className="label-caps">Selected tool</dt>
            <dd className="font-mono heading text-right">
              {response.tool_call?.tool_name || "—"}
            </dd>
          </dl>
        </>
      )}

      {response.intent && Object.keys(response.intent.entities || {}).length > 0 && (
        <div>
          <p className="label-caps mb-1">Entities</p>
          <pre className="json-viewer">
            {JSON.stringify(response.intent.entities, null, 2)}
          </pre>
        </div>
      )}

      {/* Warnings — subordinate to the outcome, never a heavy banner */}
      {response.warnings && response.warnings.length > 0 && (
        <div className="border-l-2 border-current tone-pending pl-3 py-1 text-xs">
          <div className="flex items-center gap-1.5 font-medium mb-0.5">
            <AlertTriangle className="h-3 w-3" />
            {response.warnings.length === 1 ? "Warning" : `${response.warnings.length} warnings`}
          </div>
          <ul className="space-y-0.5 text-zinc-600 dark:text-zinc-400">
            {response.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {response.result?.data && Object.keys(response.result.data).length > 0 && (
        <div>
          <p className="label-caps mb-1">Result data</p>
          <pre className="json-viewer max-h-80">
            {JSON.stringify(response.result.data, null, 2)}
          </pre>
        </div>
      )}

      {response.result?.stdout && (
        <div>
          <p className="label-caps mb-1">Output</p>
          <pre className="rounded-md bg-zinc-950 text-zinc-100 p-3 text-xs font-mono overflow-auto max-h-80 ring-1 ring-zinc-800">
            {response.result.stdout}
          </pre>
        </div>
      )}
    </div>
  );
}
