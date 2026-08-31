"use client";

import { CheckCircle2, XCircle, AlertTriangle, Zap, Activity } from "lucide-react";
import type { ExecuteResponse } from "@/lib/api";

interface Props {
  response: ExecuteResponse | null;
}

const STATUS_COLORS: Record<string, string> = {
  success:
    "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/20",
  failed:
    "bg-red-50 text-red-700 ring-red-200 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/20",
  blocked:
    "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/20",
  dry_run:
    "bg-indigo-50 text-indigo-700 ring-indigo-200 dark:bg-indigo-500/10 dark:text-indigo-300 dark:ring-indigo-500/20",
  running:
    "bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-500/10 dark:text-blue-300 dark:ring-blue-500/20",
  pending: "bg-slate-50 text-slate-700 ring-slate-200 dark:bg-slate-800 dark:text-slate-300",
};

export default function ResultsDisplay({ response }: Props) {
  if (!response) return null;

  const isSuccess = response.status === "success" || response.status === "dry_run";
  const StatusIcon = isSuccess
    ? CheckCircle2
    : response.status === "blocked"
      ? AlertTriangle
      : response.status === "running" || response.status === "pending"
        ? Activity
        : XCircle;

  const color = STATUS_COLORS[response.status] || STATUS_COLORS.pending;
  const iconColor = isSuccess
    ? "text-emerald-600 dark:text-emerald-400"
    : response.status === "blocked"
      ? "text-amber-600 dark:text-amber-400"
      : "text-red-600 dark:text-red-400";

  return (
    <div className="card p-6 space-y-4">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-3">
          <StatusIcon className={"h-6 w-6 mt-0.5 " + iconColor} />
          <div>
            <h2 className="font-semibold text-lg heading">
              Task #{response.task_id}
            </h2>
            <p className="text-sm muted">
              {response.summary || response.error || "No summary"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={"badge ring-1 " + color}>{response.status}</span>
          {response.duration_ms !== undefined && (
            <span className="badge bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              <Zap className="h-3 w-3" /> {response.duration_ms} ms
            </span>
          )}
        </div>
      </div>

      {response.intent && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <InfoCard label="Detected Intent" value={response.intent.intent} />
          <InfoCard
            label="Confidence"
            value={`${(response.intent.confidence * 100).toFixed(0)}%`}
          />
          <InfoCard
            label="Selected Tool"
            value={response.tool_call?.tool_name || "—"}
          />
        </div>
      )}

      {response.intent &&
        Object.keys(response.intent.entities || {}).length > 0 && (
          <div>
            <p className="text-xs font-medium uppercase muted mb-1 tracking-wider">
              Extracted Entities
            </p>
            <pre className="json-viewer">
              {JSON.stringify(response.intent.entities, null, 2)}
            </pre>
          </div>
        )}

      {response.warnings && response.warnings.length > 0 && (
        <div className="rounded-lg bg-amber-50 ring-1 ring-amber-200 p-3 text-sm text-amber-800
                        dark:bg-amber-500/10 dark:text-amber-200 dark:ring-amber-500/20">
          <div className="flex items-center gap-2 font-medium mb-1">
            <AlertTriangle className="h-4 w-4" /> Warnings
          </div>
          <ul className="list-disc list-inside space-y-0.5">
            {response.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {response.error && (
        <div className="rounded-lg bg-red-50 ring-1 ring-red-200 p-3 text-sm text-red-800
                        dark:bg-red-500/10 dark:text-red-200 dark:ring-red-500/20">
          <div className="flex items-center gap-2 font-medium mb-1">
            <XCircle className="h-4 w-4" /> Error
          </div>
          <p>{response.error}</p>
        </div>
      )}

      {response.result?.data &&
        Object.keys(response.result.data).length > 0 && (
          <div>
            <p className="text-xs font-medium uppercase muted mb-1 tracking-wider">
              Result Data
            </p>
            <pre className="rounded-lg bg-slate-900 text-slate-100 p-4 text-xs font-mono overflow-auto max-h-80 dark:bg-slate-950">
              {JSON.stringify(response.result.data, null, 2)}
            </pre>
          </div>
        )}

      {response.result?.stdout && (
        <div>
          <p className="text-xs font-medium uppercase muted mb-1 tracking-wider">
            Output
          </p>
          <pre className="rounded-lg bg-slate-900 text-green-300 p-4 text-xs font-mono overflow-auto max-h-80 dark:bg-slate-950">
            {response.result.stdout}
          </pre>
        </div>
      )}
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/50 dark:ring-1 dark:ring-slate-800">
      <p className="text-xs uppercase font-medium muted tracking-wider">{label}</p>
      <p className="mt-1 font-mono text-sm heading break-all">{value}</p>
    </div>
  );
}
