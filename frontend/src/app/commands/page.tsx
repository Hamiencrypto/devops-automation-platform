"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import DashboardShell from "@/components/layout/DashboardShell";
import CommandInput from "@/components/CommandInput";
import ResultsDisplay from "@/components/ResultsDisplay";
import TaskHistory from "@/components/TaskHistory";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import { useCommandRunner } from "@/lib/useCommandRunner";

const CATEGORIES: { title: string; items: { cmd: string; note: string }[] }[] = [
  {
    title: "Docker",
    items: [
      { cmd: "deploy nginx on port 8080", note: "Spin up any image with or without a port" },
      { cmd: "deploy rabbitmq", note: "Typo-tolerant image resolution" },
      { cmd: "list all containers", note: "Inspect every container on the host" },
      { cmd: "stop abc123def456", note: "Stop by container ID — destructive, needs confirmation" },
      { cmd: "remove my-nginx", note: "Remove by name — destructive, needs confirmation" },
    ],
  },
  {
    title: "System & files",
    items: [
      { cmd: "system health", note: "CPU, memory, disk snapshot" },
      { cmd: "disk usage", note: "Filesystem breakdown" },
      { cmd: "count lines in /data/app.log", note: "File stats" },
      { cmd: "analyze logs at /data/sample.log", note: "Error patterns" },
    ],
  },
];

export default function CommandsPage() {
  const { response, loading, error, pendingConfirm, run, confirmAndRun, cancelConfirm } =
    useCommandRunner();
  const [refreshKey, setRefreshKey] = useState(0);
  const [draft, setDraft] = useState<string | null>(null);

  async function handleExecute(command: string, dryRun: boolean) {
    await run(command, dryRun);
    setRefreshKey((k) => k + 1);
  }

  return (
    <DashboardShell title="Commands">
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2 space-y-3.5">
          <CommandInput
            onExecute={handleExecute}
            loading={loading}
            initialValue={draft ?? undefined}
          />

          {error && (
            <div className="tone-failed text-sm rounded-md border-l-2 border-current pl-3 py-1.5">
              {error}
            </div>
          )}

          {response && <ResultsDisplay response={response} />}

          <TaskHistory refreshKey={refreshKey} limit={8} />
        </div>

        <aside>
          <div className="card p-4">
            <div className="flex items-center gap-1.5 mb-3">
              <Sparkles className="h-3.5 w-3.5 text-zinc-400" />
              <h3 className="text-sm font-medium heading">Example playbook</h3>
            </div>
            <div className="space-y-3.5">
              {CATEGORIES.map((cat) => (
                <div key={cat.title}>
                  <p className="label-caps mb-1.5">{cat.title}</p>
                  <div className="space-y-1">
                    {cat.items.map((it) => (
                      <button
                        key={it.cmd}
                        type="button"
                        onClick={() => setDraft(it.cmd)}
                        className="w-full text-left p-2 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                      >
                        <div className="font-mono text-xs heading truncate">{it.cmd}</div>
                        <div className="text-[11px] muted mt-0.5">{it.note}</div>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>

      <ConfirmDialog
        open={!!pendingConfirm}
        busy={loading}
        intent="warn"
        title="Confirm destructive action"
        message={
          <>
            <span className="font-mono text-xs">{pendingConfirm?.command}</span> requires
            explicit confirmation before it runs.
            {response?.error && <p className="mt-2">{response.error}</p>}
          </>
        }
        confirmLabel="Run anyway"
        onCancel={cancelConfirm}
        onConfirm={confirmAndRun}
      />
    </DashboardShell>
  );
}
