"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  CheckCircle2,
  Boxes,
  Wrench,
  ArrowUpRight,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import CommandInput from "@/components/CommandInput";
import ResultsDisplay from "@/components/ResultsDisplay";
import TaskHistory from "@/components/TaskHistory";
import DashboardShell from "@/components/layout/DashboardShell";
import {
  executeCommand,
  fetchTasks,
  fetchTools,
  fetchContainers,
  type ExecuteResponse,
  type TaskOut,
} from "@/lib/api";

interface Stats {
  totalTasks: number;
  successRate: number;
  managedContainers: number;
  totalContainers: number;
  tools: number;
}

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ElementType;
  accent: string;
}) {
  return (
    <div className="stat-card group">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs uppercase font-medium muted tracking-wider">
            {label}
          </p>
          <p className="text-3xl font-bold heading mt-2 leading-none">
            {value}
          </p>
          {sub && <p className="text-xs muted mt-2">{sub}</p>}
        </div>
        <div
          className={
            "h-11 w-11 rounded-xl flex items-center justify-center shrink-0 " +
            accent
          }
        >
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

export default function HomePage() {
  const [response, setResponse] = useState<ExecuteResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
      const managed = (containerRes.containers || []).filter(
        (c) => c.managed
      ).length;

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
  }, [refreshKey]);

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
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <DashboardShell title="Dashboard">
      <div className="space-y-6">
        {/* Hero */}
        <section className="relative rounded-2xl overflow-hidden p-6 md:p-8
                            bg-gradient-to-br from-brand-500 via-brand-600 to-brand-800
                            text-white shadow-glow">
          <div className="relative z-10 max-w-3xl">
            <div className="inline-flex items-center gap-1 text-xs font-medium bg-white/15
                            px-2.5 py-1 rounded-full mb-3 backdrop-blur">
              <Sparkles className="h-3 w-3" />
              Natural-language DevOps automation
            </div>
            <h2 className="text-2xl md:text-3xl font-bold leading-tight">
              Ship, inspect and operate your stack with one sentence.
            </h2>
            <p className="mt-2 text-sm md:text-base text-white/85 max-w-2xl">
              Type what you want in plain English — the MCP router picks the right
              tool and runs it safely with dry-run and destructive-action confirmation.
            </p>
          </div>
          <div
            className="pointer-events-none absolute -right-20 -bottom-20 h-64 w-64
                       rounded-full bg-white/10 blur-3xl"
          />
          <div
            className="pointer-events-none absolute right-10 top-4 h-32 w-32
                       rounded-full bg-white/10 blur-2xl"
          />
        </section>

        {/* Stat grid */}
        <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total tasks"
            value={stats.totalTasks}
            sub="All routed through MCP"
            icon={Activity}
            accent="bg-brand-100 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300"
          />
          <StatCard
            label="Success rate"
            value={`${stats.successRate}%`}
            sub="Completed + dry-runs"
            icon={CheckCircle2}
            accent="bg-emerald-100 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300"
          />
          <StatCard
            label="Managed containers"
            value={stats.managedContainers}
            sub={`of ${stats.totalContainers} total running`}
            icon={Boxes}
            accent="bg-indigo-100 text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-300"
          />
          <StatCard
            label="MCP tools"
            value={stats.tools}
            sub="Registered and ready"
            icon={Wrench}
            accent="bg-amber-100 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300"
          />
        </section>

        {/* Command + quick links */}
        <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-2 space-y-6">
            <CommandInput onExecute={handleExecute} loading={loading} />

            {error && (
              <div className="rounded-lg bg-red-50 ring-1 ring-red-200 p-4 text-sm text-red-800
                              dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/20">
                <strong>Request failed:</strong> {error}
              </div>
            )}

            {response && <ResultsDisplay response={response} />}
          </div>

          <aside className="space-y-4">
            <div className="card p-5">
              <div className="flex items-center gap-2 mb-3">
                <div className="h-8 w-8 rounded-lg bg-brand-50 text-brand-600
                                flex items-center justify-center
                                dark:bg-brand-500/15 dark:text-brand-300">
                  <Boxes className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="font-semibold heading text-sm">Containers</h3>
                  <p className="text-xs muted">Stop, remove and inspect</p>
                </div>
              </div>
              <Link
                href="/containers"
                className="btn-secondary w-full justify-center text-sm"
              >
                Manage containers
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            <div className="card p-5">
              <div className="flex items-center gap-2 mb-3">
                <div className="h-8 w-8 rounded-lg bg-emerald-50 text-emerald-600
                                flex items-center justify-center
                                dark:bg-emerald-500/15 dark:text-emerald-300">
                  <Wrench className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="font-semibold heading text-sm">MCP Tools</h3>
                  <p className="text-xs muted">{stats.tools} registered</p>
                </div>
              </div>
              <Link
                href="/tools"
                className="btn-secondary w-full justify-center text-sm"
              >
                Browse catalog
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            <div className="card p-5">
              <div className="flex items-center gap-2 mb-3">
                <div className="h-8 w-8 rounded-lg bg-indigo-50 text-indigo-600
                                flex items-center justify-center
                                dark:bg-indigo-500/15 dark:text-indigo-300">
                  <Activity className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="font-semibold heading text-sm">Live Logs</h3>
                  <p className="text-xs muted">Stream task events</p>
                </div>
              </div>
              <Link
                href="/logs"
                className="btn-secondary w-full justify-center text-sm"
              >
                Open stream
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </aside>
        </section>

        {/* Recent activity */}
        <section>
          <TaskHistory refreshKey={refreshKey} limit={8} />
        </section>

        <footer className="text-center text-xs muted pt-4 pb-2">
          University of Sindh · Department of Information Technology · FYP 2025–2026
        </footer>
      </div>
    </DashboardShell>
  );
}
