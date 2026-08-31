"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ScrollText,
  RefreshCw,
  Search,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import DashboardShell from "@/components/layout/DashboardShell";
import { fetchTasks, type TaskOut } from "@/lib/api";

const PAGE_SIZE = 20;

const STATUS_PILL: Record<string, string> = {
  success: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  blocked: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  dry_run: "bg-indigo-100 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300",
  running: "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300",
  pending: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
};

const STATUS_OPTIONS = ["all", "success", "failed", "dry_run", "blocked", "running"];

export default function HistoryPage() {
  const [tasks, setTasks] = useState<TaskOut[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");

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
      <div className="space-y-5">
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <ScrollText className="h-4 w-4" />
              All Tasks
              <span className="chip ml-1">{total}</span>
            </div>
            <div className="flex items-center gap-2 flex-wrap justify-end">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 muted" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search commands…"
                  className="input pl-9 py-1.5 text-xs w-56"
                />
              </div>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="input py-1.5 text-xs w-32 capitalize"
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s.replace("_", " ")}
                  </option>
                ))}
              </select>
              <button
                onClick={() => load(page)}
                disabled={loading}
                className="btn-secondary text-xs py-1.5 px-3"
              >
                <RefreshCw
                  className={"h-3.5 w-3.5 " + (loading ? "animate-spin" : "")}
                />
                Refresh
              </button>
            </div>
          </div>

          {error && (
            <div className="m-4 text-sm text-red-700 bg-red-50 dark:bg-red-500/10 dark:text-red-300 rounded p-3">
              {error}
            </div>
          )}

          {filtered.length === 0 ? (
            <p className="text-sm muted text-center py-14">
              {loading ? "Loading tasks…" : "No tasks to show."}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-xs font-medium muted border-b border-slate-200 dark:border-slate-800">
                    <th className="py-3 pl-5 pr-4">#</th>
                    <th className="py-3 pr-4">Command</th>
                    <th className="py-3 pr-4">Intent</th>
                    <th className="py-3 pr-4">Tool</th>
                    <th className="py-3 pr-4">Status</th>
                    <th className="py-3 pr-4">Duration</th>
                    <th className="py-3 pr-4">When</th>
                    <th className="py-3 pr-5">Error</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {filtered.map((t) => (
                    <tr
                      key={t.id}
                      className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition"
                    >
                      <td className="py-3 pl-5 pr-4 font-mono text-xs muted">{t.id}</td>
                      <td className="py-3 pr-4 max-w-sm truncate heading">{t.command}</td>
                      <td className="py-3 pr-4">
                        {t.detected_intent ? (
                          <span className="chip">{t.detected_intent}</span>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td className="py-3 pr-4">
                        {t.selected_tool ? (
                          <span className="chip">{t.selected_tool}</span>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td className="py-3 pr-4">
                        <span
                          className={
                            "badge " + (STATUS_PILL[t.status] || STATUS_PILL.pending)
                          }
                        >
                          {t.status}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-xs muted">
                        {t.duration_ms !== null ? `${t.duration_ms} ms` : "—"}
                      </td>
                      <td className="py-3 pr-4 text-xs muted">
                        {new Date(t.created_at).toLocaleString()}
                      </td>
                      <td className="py-3 pr-5 text-xs text-red-600 dark:text-red-400 max-w-xs truncate">
                        {t.error_message || ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {total > 0 && (
            <div className="px-5 py-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs">
              <span className="muted">
                Page {page} of {totalPages} · {total} total tasks
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1 || loading}
                  className="btn-ghost px-2 py-1 disabled:opacity-40"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                  Prev
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages || loading}
                  className="btn-ghost px-2 py-1 disabled:opacity-40"
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
