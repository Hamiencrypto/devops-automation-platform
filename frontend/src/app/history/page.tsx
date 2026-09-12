"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ScrollText, RefreshCw, Search, ChevronLeft, ChevronRight } from "lucide-react";
import DashboardShell from "@/components/layout/DashboardShell";
import { fetchTasks, type TaskOut, type TaskStatus } from "@/lib/api";
import { getStatusMeta } from "@/lib/status";

const PAGE_SIZE = 20;
const STATUS_OPTIONS: (TaskStatus | "all")[] = [
  "all",
  "success",
  "failed",
  "dry_run",
  "blocked",
  "running",
];

export default function HistoryPage() {
  const [tasks, setTasks] = useState<TaskOut[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<TaskStatus | "all">("all");

  const load = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchTasks(p, PAGE_SIZE);
      setTasks(res.items);
      setTotal(res.total);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(page);
  }, [page, load]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tasks.filter((t) => {
      if (status !== "all" && t.status !== status) return false;
      if (!q) return true;
      return (
        t.command.toLowerCase().includes(q) ||
        (t.detected_intent || "").toLowerCase().includes(q) ||
        (t.selected_tool || "").toLowerCase().includes(q)
      );
    });
  }, [tasks, query, status]);

  return (
    <DashboardShell title="Task History">
      <div className="space-y-4">
        <div className="card">
          <div className="card-header flex-wrap">
            <div className="card-title">
              <ScrollText className="h-4 w-4" />
              All tasks
              <span className="chip ml-1">{total}</span>
            </div>
            <div className="flex items-center gap-2 flex-wrap justify-end">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 muted" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search commands…"
                  aria-label="Search commands"
                  className="input pl-8 py-1.5 text-xs w-52"
                />
              </div>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as TaskStatus | "all")}
                aria-label="Filter by status"
                className="input py-1.5 text-xs w-32 capitalize"
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s.replace("_", " ")}
                  </option>
                ))}
              </select>
              <button onClick={() => load(page)} disabled={loading} className="btn-ghost text-xs py-1.5 px-2">
                <RefreshCw className={"h-3.5 w-3.5 " + (loading ? "animate-spin" : "")} />
              </button>
            </div>
          </div>

          {error && (
            <div className="m-3 tone-failed text-sm rounded p-2 border-l-2 border-current">{error}</div>
          )}

          {filtered.length === 0 ? (
            <p className="text-sm muted text-center py-12">
              {loading ? "Loading tasks…" : "No tasks to show."}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-xs font-medium muted border-b border-zinc-200 dark:border-zinc-800">
                    <th className="py-2 pl-4 pr-3 font-medium">#</th>
                    <th className="py-2 pr-3 font-medium">Command</th>
                    <th className="py-2 pr-3 font-medium">Intent</th>
                    <th className="py-2 pr-3 font-medium">Tool</th>
                    <th className="py-2 pr-3 font-medium">Status</th>
                    <th className="py-2 pr-3 font-medium text-right">Duration</th>
                    <th className="py-2 pr-3 font-medium">When</th>
                    <th className="py-2 pr-4 font-medium">Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                  {filtered.map((t) => {
                    const meta = getStatusMeta(t.status);
                    const Icon = meta.icon;
                    return (
                      <tr key={t.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-900/60 transition-colors">
                        <td className="py-2 pl-4 pr-3 font-mono text-xs muted tabular-nums">{t.id}</td>
                        <td className="py-2 pr-3 max-w-sm truncate font-mono text-xs heading">{t.command}</td>
                        <td className="py-2 pr-3">
                          {t.detected_intent ? (
                            <span className="chip">{t.detected_intent}</span>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                        <td className="py-2 pr-3">
                          {t.selected_tool ? (
                            <span className="chip">{t.selected_tool}</span>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                        <td className="py-2 pr-3">
                          <span className={"badge " + meta.badgeClass}>
                            <Icon className="h-3 w-3" />
                            {meta.label}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-xs muted text-right tabular-nums">
                          {t.duration_ms !== null ? `${t.duration_ms}ms` : "—"}
                        </td>
                        <td className="py-2 pr-3 text-xs muted tabular-nums">
                          {new Date(t.created_at).toLocaleString()}
                        </td>
                        <td className={"py-2 pr-4 text-xs max-w-xs truncate " + (t.error_message ? meta.textClass : "muted")}>
                          {t.error_message || ""}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {total > 0 && (
            <div className="px-4 py-2.5 border-t border-zinc-200 dark:border-zinc-800 flex items-center justify-between text-xs">
              <span className="muted">
                Page {page} of {totalPages} · {total} total
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1 || loading}
                  className="btn-ghost px-1.5 py-1 disabled:opacity-40"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                  Prev
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages || loading}
                  className="btn-ghost px-1.5 py-1 disabled:opacity-40"
                >
                  Next
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </DashboardShell>
  );
}
