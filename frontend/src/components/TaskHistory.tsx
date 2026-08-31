"use client";

import { useEffect, useState } from "react";
import { History, RefreshCw } from "lucide-react";
import { fetchTasks, type TaskOut } from "@/lib/api";

const STATUS_PILL: Record<string, string> = {
  success:
    "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  blocked: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  dry_run: "bg-indigo-100 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300",
  running: "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300",
  pending: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
};

export default function TaskHistory({
  refreshKey = 0,
  limit = 10,
  compact,
}: {
  refreshKey?: number;
  limit?: number;
  compact?: boolean;
}) {
  const [tasks, setTasks] = useState<TaskOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchTasks(1, limit);
      setTasks(res.items);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <History className="h-4 w-4" />
          Task History
        </div>
        <button
          className="btn-secondary text-xs py-1.5 px-3"
          onClick={load}
          disabled={loading}
        >
          <RefreshCw
            className={"h-3.5 w-3.5 " + (loading ? "animate-spin" : "")}
          />
          Refresh
        </button>
      </div>

      <div className={compact ? "p-0" : ""}>
        {error && (
          <div className="m-4 text-sm text-red-600 bg-red-50 dark:bg-red-500/10 dark:text-red-300 rounded p-3">
            {error}
          </div>
        )}

        {tasks.length === 0 && !loading ? (
          <p className="text-sm muted text-center py-10">
            No tasks yet. Run a command to see it here.
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
                  <th className="py-3 pr-5">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {tasks.map((t) => (
                  <tr
                    key={t.id}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition"
                  >
                    <td className="py-3 pl-5 pr-4 font-mono text-xs muted">
                      {t.id}
                    </td>
                    <td className="py-3 pr-4 max-w-xs truncate heading">
                      {t.command}
                    </td>
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
                          "badge " +
                          (STATUS_PILL[t.status] || STATUS_PILL.pending)
                        }
                      >
                        {t.status}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-xs muted">
                      {t.duration_ms !== null ? `${t.duration_ms} ms` : "—"}
                    </td>
                    <td className="py-3 pr-5 text-xs muted">
                      {new Date(t.created_at).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
