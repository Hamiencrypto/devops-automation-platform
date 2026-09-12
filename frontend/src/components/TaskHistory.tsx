"use client";

import { useEffect, useState } from "react";
import { History, RefreshCw } from "lucide-react";
import { fetchTasks, type TaskOut } from "@/lib/api";
import { getStatusMeta } from "@/lib/status";

export default function TaskHistory({
  refreshKey = 0,
  limit = 10,
}: {
  refreshKey?: number;
  limit?: number;
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
          Task history
        </div>
        <button className="btn-ghost text-xs py-1 px-2" onClick={load} disabled={loading}>
          <RefreshCw className={"h-3.5 w-3.5 " + (loading ? "animate-spin" : "")} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="m-3 tone-failed text-sm rounded p-2 border-l-2 border-current">
          {error}
        </div>
      )}

      {tasks.length === 0 && !loading ? (
        <p className="text-sm muted text-center py-8">
          No tasks yet. Run a command to see it here.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs font-medium muted border-b border-black/5 dark:border-white/10">
                <th className="py-2 pl-4 pr-3 font-medium">#</th>
                <th className="py-2 pr-3 font-medium">Command</th>
                <th className="py-2 pr-3 font-medium">Intent</th>
                <th className="py-2 pr-3 font-medium">Tool</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium text-right">Duration</th>
                <th className="py-2 pr-4 font-medium text-right">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-black/5 dark:divide-white/10">
              {tasks.map((t) => {
                const meta = getStatusMeta(t.status);
                const Icon = meta.icon;
                return (
                  <tr key={t.id} className="hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                    <td className="py-2 pl-4 pr-3 font-mono text-xs muted tabular-nums">{t.id}</td>
                    <td className="py-2 pr-3 max-w-xs truncate font-mono text-xs heading">
                      {t.command}
                    </td>
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
                    <td className="py-2 pr-4 text-xs muted text-right tabular-nums">
                      {new Date(t.created_at).toLocaleTimeString()}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
