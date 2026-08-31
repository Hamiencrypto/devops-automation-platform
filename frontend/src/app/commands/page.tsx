"use client";

import { useState } from "react";
import { Terminal, Sparkles } from "lucide-react";
import DashboardShell from "@/components/layout/DashboardShell";
import CommandInput from "@/components/CommandInput";
import ResultsDisplay from "@/components/ResultsDisplay";
import TaskHistory from "@/components/TaskHistory";
import { executeCommand, type ExecuteResponse } from "@/lib/api";

const CATEGORIES: { title: string; items: { cmd: string; note: string }[] }[] = [
  {
    title: "Docker",
    items: [
      { cmd: "deploy nginx on port 8080", note: "Spin up any image with or without a port" },
      { cmd: "deploy rabbitmq", note: "Typo-tolerant image resolution" },
      { cmd: "deploy mongodb on port 27017", note: "Alias → mongo:latest" },
      { cmd: "list all containers", note: "Inspect every container on the host" },
      { cmd: "stop abc123def456", note: "Stop by container ID" },
      { cmd: "remove my-nginx", note: "Remove by name" },
    ],
  },
  {
    title: "System & Files",
    items: [
      { cmd: "system health", note: "CPU, memory, disk snapshot" },
      { cmd: "disk usage", note: "Filesystem breakdown" },
      { cmd: "count lines in /data/app.log", note: "File stats" },
      { cmd: "analyze logs at /data/sample.log", note: "Error patterns" },
    ],
  },
];

export default function CommandsPage() {
  const [response, setResponse] = useState<ExecuteResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [draft, setDraft] = useState<string | null>(null);

  async function handleExecute(
    command: string,
    opts: { dry_run: boolean; confirm_destructive: boolean }
  ) {
    setLoading(true);
    setError(null);
    try {
      const res = await executeCommand(command, opts);
      setResponse(res);
      setRefreshKey((k) => k + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <DashboardShell title="Commands">
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <div className="xl:col-span-2 space-y-5">
          <div className="card p-5">
            <div className="flex items-center gap-3 mb-4">
              <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white flex items-center justify-center shadow-glow">
                <Terminal className="h-5 w-5" />
              </div>
              <div>
                <h2 className="font-semibold heading">Natural-language command runner</h2>
                <p className="text-xs muted">
                  The MCP router selects a tool, verifies safety, and executes.
                </p>
              </div>
            </div>
            <CommandInput
              onExecute={handleExecute}
              loading={loading}
              compact
              initialValue={draft ?? undefined}
            />
          </div>

          {error && (
            <div className="rounded-lg bg-red-50 ring-1 ring-red-200 p-4 text-sm text-red-800
                            dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/20">
              <strong>Request failed:</strong> {error}
            </div>
          )}

          {response && <ResultsDisplay response={response} />}

          <TaskHistory refreshKey={refreshKey} limit={8} />
        </div>

        <aside className="space-y-4">
          <div className="card p-5">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="h-4 w-4 text-brand-500" />
              <h3 className="font-semibold heading text-sm">Example playbook</h3>
            </div>
            <div className="space-y-4">
              {CATEGORIES.map((cat) => (
                <div key={cat.title}>
                  <p className="text-[10px] font-bold uppercase tracking-wider muted mb-2">
                    {cat.title}
                  </p>
                  <div className="space-y-1.5">
                    {cat.items.map((it) => (
                      <button
                        key={it.cmd}
                        type="button"
                        onClick={() => setDraft(it.cmd)}
                        className="w-full text-left p-2.5 rounded-lg bg-slate-50 hover:bg-brand-50
                                   border border-transparent hover:border-brand-200 transition
                                   dark:bg-slate-800/60 dark:hover:bg-brand-500/10 dark:hover:border-brand-500/30"
                      >
                        <div className="font-mono text-xs heading truncate">
                          {it.cmd}
                        </div>
                        <div className="text-[10px] muted mt-0.5">{it.note}</div>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            {draft && (
              <p className="mt-3 text-[10px] muted italic">
                Tip: clicked sample copied into the input above.
              </p>
            )}
          </div>
        </aside>
      </div>
    </DashboardShell>
  );
}
