"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Boxes,
  RefreshCw,
  Search,
  Square,
  Trash2,
  Copy,
  CheckCircle2,
  Filter,
  Shield,
  Circle,
} from "lucide-react";
import DashboardShell from "@/components/layout/DashboardShell";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import {
  fetchContainers,
  stopContainer,
  removeContainer,
  type ContainerInfo,
} from "@/lib/api";

type FilterKind = "all" | "managed" | "running" | "stopped";

function statusTone(status: string) {
  const s = (status || "").toLowerCase();
  if (s.includes("running") || s.includes("up"))
    return "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300";
  if (s.includes("exited") || s.includes("stopped") || s.includes("dead"))
    return "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300";
  if (s.includes("paused"))
    return "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300";
  if (s.includes("restart"))
    return "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300";
  return "bg-indigo-100 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300";
}

function formatPorts(ports: unknown): string {
  if (!ports || typeof ports !== "object") return "—";
  const entries = Object.entries(ports as Record<string, unknown>);
  if (entries.length === 0) return "—";
  const parts: string[] = [];
  for (const [key, value] of entries) {
    if (Array.isArray(value) && value.length > 0) {
      const mapped = value
        .map((v) => {
          if (v && typeof v === "object" && "HostPort" in v) {
            const hp = (v as { HostPort?: string }).HostPort;
            return hp ? `${hp}→${key}` : key;
          }
          return key;
        })
        .join(", ");
      parts.push(mapped);
    } else {
      parts.push(key);
    }
  }
  return parts.join(", ");
}

export default function ContainersPage() {
  const { user } = useAuth();
  const { push } = useToast();
  const [containers, setContainers] = useState<ContainerInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<FilterKind>("all");
  const [confirmAction, setConfirmAction] = useState<
    | { kind: "stop" | "remove"; container: ContainerInfo }
    | null
  >(null);

  const canMutate = !user || user.role !== "viewer";

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchContainers();
      setContainers(res.containers);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, [load]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return containers.filter((c) => {
      if (filter === "managed" && !c.managed) return false;
      if (filter === "running" && !(c.status || "").toLowerCase().includes("running"))
        return false;
      if (
        filter === "stopped" &&
        !["exited", "stopped", "dead", "created"].some((s) =>
          (c.status || "").toLowerCase().includes(s)
        )
      )
        return false;
      if (!q) return true;
      return (
        c.id.toLowerCase().includes(q) ||
        (c.name || "").toLowerCase().includes(q) ||
        (c.image || "").toLowerCase().includes(q) ||
        (c.status || "").toLowerCase().includes(q)
      );
    });
  }, [containers, query, filter]);

  async function runAction(kind: "stop" | "remove", c: ContainerInfo) {
    setBusyId(c.id);
    try {
      const res =
        kind === "stop" ? await stopContainer(c.id) : await removeContainer(c.id);
      if (res.success) {
        push(
          res.summary || `${kind === "stop" ? "Stopped" : "Removed"} ${c.name || c.id.slice(0, 12)}`,
          "success"
        );
      } else {
        push(res.summary || `Failed to ${kind} container`, "error");
      }
      await load();
    } catch (e) {
      push((e as Error).message, "error");
    } finally {
      setBusyId(null);
      setConfirmAction(null);
    }
  }

  function copyId(id: string) {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(id);
      push("Container ID copied to clipboard", "info", 2000);
    }
  }

  const counts = useMemo(() => {
    const running = containers.filter((c) =>
      (c.status || "").toLowerCase().includes("running")
    ).length;
    const managed = containers.filter((c) => c.managed).length;
    return { total: containers.length, running, managed };
  }, [containers]);

  return (
    <DashboardShell title="Containers">
      <div className="space-y-5">
        {/* Summary strip */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="stat-card">
            <p className="text-xs uppercase font-medium muted tracking-wider">Total</p>
            <p className="text-2xl font-bold heading mt-1">{counts.total}</p>
          </div>
          <div className="stat-card">
            <p className="text-xs uppercase font-medium muted tracking-wider">Running</p>
            <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
              {counts.running}
            </p>
          </div>
          <div className="stat-card">
            <p className="text-xs uppercase font-medium muted tracking-wider">Managed</p>
            <p className="text-2xl font-bold text-brand-600 dark:text-brand-400 mt-1">
              {counts.managed}
            </p>
          </div>
          <div className="stat-card">
            <p className="text-xs uppercase font-medium muted tracking-wider">Role</p>
            <p className="text-lg font-semibold heading mt-1 flex items-center gap-2">
              <Shield className="h-4 w-4 text-brand-500" />
              {user?.role || "anonymous"}
            </p>
          </div>
        </section>

        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <Boxes className="h-4 w-4" />
              Container Registry
            </div>
            <div className="flex items-center gap-2">
              <div className="relative hidden sm:block">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 muted" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search by name, image, ID…"
                  className="input pl-9 py-1.5 text-xs w-60"
                />
              </div>
              <div className="hidden md:flex items-center gap-1 rounded-lg bg-slate-100 dark:bg-slate-800 p-1">
                {(["all", "running", "stopped", "managed"] as FilterKind[]).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={
                      "text-xs px-2 py-1 rounded-md capitalize transition " +
                      (filter === f
                        ? "bg-white shadow-sm heading dark:bg-slate-900"
                        : "muted hover:text-slate-900 dark:hover:text-slate-100")
                    }
                  >
                    {f}
                  </button>
                ))}
              </div>
              <button
                onClick={load}
                disabled={loading}
                className="btn-secondary text-xs py-1.5 px-3"
                title="Refresh"
              >
                <RefreshCw
                  className={"h-3.5 w-3.5 " + (loading ? "animate-spin" : "")}
                />
                Refresh
              </button>
            </div>
          </div>

          {/* Mobile search */}
          <div className="sm:hidden px-4 pt-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 muted" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search…"
                className="input pl-9 py-1.5 text-sm w-full"
              />
            </div>
            <div className="flex gap-1 mt-2 overflow-x-auto">
              {(["all", "running", "stopped", "managed"] as FilterKind[]).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={
                    "text-xs px-3 py-1 rounded-full capitalize whitespace-nowrap " +
                    (filter === f
                      ? "bg-brand-500 text-white"
                      : "bg-slate-100 dark:bg-slate-800 muted")
                  }
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div
              className="m-4 text-sm text-red-700 bg-red-50 dark:bg-red-500/10 dark:text-red-300
                         rounded-lg p-3 flex items-center gap-2"
            >
              <Filter className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          {filtered.length === 0 ? (
            <div className="py-14 text-center">
              <div
                className="h-14 w-14 mx-auto rounded-2xl bg-slate-100 dark:bg-slate-800
                           flex items-center justify-center mb-3"
              >
                <Boxes className="h-7 w-7 muted" />
              </div>
              <p className="text-sm muted">
                {loading
                  ? "Loading containers…"
                  : containers.length === 0
                    ? "No containers found on this Docker host."
                    : "No containers match your filters."}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-xs font-medium muted border-b border-slate-200 dark:border-slate-800">
                    <th className="py-3 pl-5 pr-4">Name</th>
                    <th className="py-3 pr-4">Container ID</th>
                    <th className="py-3 pr-4">Image</th>
                    <th className="py-3 pr-4">Status</th>
                    <th className="py-3 pr-4">Ports</th>
                    <th className="py-3 pr-5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {filtered.map((c) => {
                    const shortId = c.id.slice(0, 12);
                    const running = (c.status || "").toLowerCase().includes("running");
                    const isBusy = busyId === c.id;
                    return (
                      <tr
                        key={c.id}
                        className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition"
                      >
                        <td className="py-3 pl-5 pr-4">
                          <div className="flex items-center gap-2 min-w-0">
                            <Circle
                              className={
                                "h-2 w-2 shrink-0 " +
                                (running
                                  ? "fill-emerald-500 text-emerald-500"
                                  : "fill-slate-400 text-slate-400")
                              }
                            />
                            <div className="min-w-0">
                              <div className="font-medium heading truncate max-w-[12rem]">
                                {c.name || "(unnamed)"}
                              </div>
                              {c.managed && (
                                <div className="text-[10px] text-brand-600 dark:text-brand-400 mt-0.5 inline-flex items-center gap-1">
                                  <Shield className="h-2.5 w-2.5" />
                                  managed by MCP
                                </div>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="py-3 pr-4">
                          <button
                            type="button"
                            onClick={() => copyId(c.id)}
                            className="group inline-flex items-center gap-1.5 font-mono text-xs
                                       px-2 py-1 rounded bg-slate-100 dark:bg-slate-800
                                       hover:bg-brand-100 dark:hover:bg-brand-500/15 transition"
                            title={"Click to copy full ID: " + c.id}
                          >
                            {shortId}
                            <Copy className="h-3 w-3 opacity-50 group-hover:opacity-100" />
                          </button>
                        </td>
                        <td className="py-3 pr-4 font-mono text-xs truncate max-w-[14rem]">
                          {c.image || "—"}
                        </td>
                        <td className="py-3 pr-4">
                          <span className={"badge " + statusTone(c.status)}>
                            {c.status || "unknown"}
                          </span>
                        </td>
                        <td className="py-3 pr-4 text-xs muted max-w-[12rem] truncate">
                          {formatPorts(c.ports)}
                        </td>
                        <td className="py-3 pr-5">
                          <div className="flex items-center justify-end gap-1.5">
                            {canMutate && running && (
                              <button
                                type="button"
                                onClick={() =>
                                  setConfirmAction({ kind: "stop", container: c })
                                }
                                disabled={isBusy}
                                className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md
                                           bg-amber-50 text-amber-700 hover:bg-amber-100
                                           disabled:opacity-50 disabled:cursor-not-allowed
                                           dark:bg-amber-500/10 dark:text-amber-300 dark:hover:bg-amber-500/20"
                                title="Stop container"
                              >
                                <Square className="h-3 w-3" />
                                Stop
                              </button>
                            )}
                            {canMutate && (
                              <button
                                type="button"
                                onClick={() =>
                                  setConfirmAction({ kind: "remove", container: c })
                                }
                                disabled={isBusy}
                                className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md
                                           bg-red-50 text-red-700 hover:bg-red-100
                                           disabled:opacity-50 disabled:cursor-not-allowed
                                           dark:bg-red-500/10 dark:text-red-300 dark:hover:bg-red-500/20"
                                title="Remove container"
                              >
                                <Trash2 className="h-3 w-3" />
                                Remove
                              </button>
                            )}
                            {!canMutate && (
                              <span className="text-[10px] muted italic">
                                read-only
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {!loading && containers.length > 0 && (
            <div className="px-5 py-3 border-t border-slate-200 dark:border-slate-800
                            text-xs muted flex items-center justify-between flex-wrap gap-2">
              <span>
                Showing {filtered.length} of {containers.length} containers
              </span>
              <span className="inline-flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                Auto-refresh every 10s
              </span>
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={!!confirmAction}
        busy={busyId !== null}
        title={
          confirmAction?.kind === "stop" ? "Stop this container?" : "Remove this container?"
        }
        message={
          confirmAction ? (
            <div className="space-y-2">
              <p>
                {confirmAction.kind === "stop"
                  ? "This will send a SIGTERM to the container and wait for it to stop gracefully."
                  : "This will permanently remove the container. Its data will be lost unless it was persisted to a volume."}
              </p>
              <div className="rounded-lg bg-slate-50 dark:bg-slate-800/60 p-2 text-xs font-mono">
                <div>
                  <span className="muted">ID:&nbsp;&nbsp;&nbsp;</span>
                  {confirmAction.container.id.slice(0, 24)}
                </div>
                <div>
                  <span className="muted">Name:&nbsp;</span>
                  {confirmAction.container.name || "(unnamed)"}
                </div>
                <div>
                  <span className="muted">Image:</span>{" "}
                  {confirmAction.container.image}
                </div>
              </div>
            </div>
          ) : (
            ""
          )
        }
        confirmLabel={confirmAction?.kind === "stop" ? "Stop container" : "Remove container"}
        intent={confirmAction?.kind === "stop" ? "warn" : "danger"}
        onCancel={() => setConfirmAction(null)}
        onConfirm={() => {
          if (confirmAction) runAction(confirmAction.kind, confirmAction.container);
        }}
      />
    </DashboardShell>
  );
}
