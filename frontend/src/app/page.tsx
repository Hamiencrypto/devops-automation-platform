"use client";

import { useEffect, useState } from "react";
import { Activity, CheckCircle2, Boxes, Wrench } from "lucide-react";
import CommandInput from "@/components/CommandInput";
import ResultsDisplay from "@/components/ResultsDisplay";
import TaskHistory from "@/components/TaskHistory";
import DashboardShell from "@/components/layout/DashboardShell";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import { useCommandRunner } from "@/lib/useCommandRunner";
import {
  fetchTasks,
  fetchTools,
  fetchContainers,
  type TaskOut,
} from "@/lib/api";

interface Stats {
  totalTasks: number;
  successRate: number;
  managedContainers: number;
  totalContainers: number;
  tools: number;
}

const STAT_TINTS = [
  "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400",
  "bg-violet-500/10 text-violet-600 dark:text-violet-400",
] as const;

function StatCard({
  label,
  value,
  icon: Icon,
  tint,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  tint: (typeof STAT_TINTS)[number];
}) {
  return (
    <div className="card p-3.5 flex items-center gap-3">
      <div className={"h-9 w-9 rounded-xl flex items-center justify-center shrink-0 " + tint}>
        <Icon className="h-4.5 w-4.5" />
      </div>
      <div className="min-w-0">
        <p className="text-lg font-semibold heading leading-none tabular-nums">{value}</p>
        <p className="label-caps mt-1">{label}</p>
      </div>
    </div>
  );
}

export default function HomePage() {
  const { response, loading, error, pendingConfirm, run, confirmAndRun, cancelConfirm } =
    useCommandRunner();
  const [refreshKey, setRefreshKey] = useState(0);

  const [stats, setStats] = useState<Stats>({
    totalTasks: 0,
    successRate: 0,
    managedContainers: 0,
    totalContainers: 0,
    tools: 0,
  });

  async function loadStats() {
    try {
      const [taskRes, toolRes, containerRes] = await Promise.all([
        fetchTasks(1, 100).catch(() => ({ total: 0, items: [] as TaskOut[] })),
        fetchTools().catch(() => ({ total: 0, tools: [] })),
        fetchContainers().catch(() => ({ total: 0, containers: [] })),
      ]);
      const items = taskRes.items || [];
      const finished = items.filter(
        (t) => t.status === "success" || t.status === "failed" || t.status === "dry_run"
      );
      const success = finished.filter(
        (t) => t.status === "success" || t.status === "dry_run"
      ).length;
      const rate =
        finished.length === 0 ? 0 : Math.round((success / finished.length) * 100);
      const managed = (containerRes.containers || []).filter((c) => c.managed).length;

      setStats({
        totalTasks: taskRes.total || items.length,
        successRate: rate,
        managedContainers: managed,
        totalContainers: containerRes.total || (containerRes.containers || []).length,
        tools: toolRes.total || (toolRes.tools || []).length,
      });
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    loadStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  async function handleExecute(command: string, dryRun: boolean) {
    await run(command, dryRun);
    setRefreshKey((k) => k + 1);
  }

  return (
    <DashboardShell title="Dashboard">
      <div className="space-y-5">
        <section className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard label="Total tasks" value={stats.totalTasks} icon={Activity} tint={STAT_TINTS[0]} />
          <StatCard label="Success rate" value={`${stats.successRate}%`} icon={CheckCircle2} tint={STAT_TINTS[1]} />
          <StatCard
            label="Managed containers"
            value={`${stats.managedContainers} / ${stats.totalContainers}`}
            icon={Boxes}
            tint={STAT_TINTS[2]}
          />
          <StatCard label="MCP tools" value={stats.tools} icon={Wrench} tint={STAT_TINTS[3]} />
        </section>

        <section className="space-y-3.5">
          <CommandInput onExecute={handleExecute} loading={loading} />

          {error && (
            <div className="tone-failed text-sm rounded-md border-l-2 border-current pl-3 py-1.5">
              {error}
            </div>
          )}

          {response && <ResultsDisplay response={response} />}
        </section>

        <TaskHistory refreshKey={refreshKey} limit={8} />

        <footer className="text-center text-xs muted pt-2 pb-1">
          University of Sindh · Department of Information Technology · FYP 2025–2026
        </footer>
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
