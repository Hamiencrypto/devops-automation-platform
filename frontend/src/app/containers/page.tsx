"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Boxes,
  RefreshCw,
  Search,
  Square,
  Trash2,
  Copy,
  ShieldCheck,
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
  isPolicyDenied,
  type ContainerInfo,
} from "@/lib/api";

type FilterKind = "all" | "managed" | "running" | "stopped";

function statusTone(status: string) {
  const s = (status || "").toLowerCase();
  if (s.includes("running") || s.includes("up")) return "badge-success";
  if (s.includes("exited") || s.includes("stopped") || s.includes("dead")) return "badge-neutral";
  if (s.includes("paused")) return "badge-pending";
  return "badge-neutral";
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
    { kind: "stop" | "remove"; container: ContainerInfo } | null
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
      const res = kind === "stop" ? await stopContainer(c.id) : await removeContainer(c.id);
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
      // A 403 here is the safety boundary refusing the action, not a
      // failure of the action — distinct toast, distinct colour, distinct
      // icon, same as every other place this app shows a policy decision.
      if (isPolicyDenied(e)) {
        push(e.message, "denied", 6000);
      } else {
        push((e as Error).message, "error");
      }
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
    const running = containers.filter((c) => (c.status || "").toLowerCase().includes("running")).length;
    const managed = containers.filter((c) => c.managed).length;
    return { total: containers.length, running, managed };
  }, [containers]);

  return (
    <DashboardShell title="Containers">
      <div className="space-y-4">
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="card p-3.5">
            <p className="label-caps">Total</p>
            <p className="text-xl font-semibold heading mt-1 tabular-nums">{counts.total}</p>
          </div>
          <div className="card p-3.5">
            <p className="label-caps">Running</p>
            <p className="text-xl font-semibold tone-success mt-1 tabular-nums">{counts.running}</p>
          </div>
          <div className="card p-3.5">
            <p className="label-caps">Managed</p>
            <p className="text-xl font-semibold heading mt-1 tabular-nums">{counts.managed}</p>
          </div>
          <div className="card p-3.5">
            <p className="label-caps">Role</p>
            <p className="text-sm font-medium heading mt-1.5 flex items-center gap-1.5 capitalize">
              <ShieldCheck className="h-3.5 w-3.5 text-zinc-400" />
              {user?.role || "anonymous"}
            </p>
          </div>
        </section>

        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <Boxes className="h-4 w-4" />
              Container registry
            </div>
            <div className="flex items-center gap-2">
              <div className="relative hidden sm:block">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 muted" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search…"
                  aria-label="Search containers"
                  className="input pl-8 py-1.5 text-xs w-52"
                />
              </div>
              <div className="hidden md:flex items-center gap-0.5 rounded-md bg-zinc-100 dark:bg-zinc-800 p-0.5">
                {(["all", "running", "stopped", "managed"] as FilterKind[]).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={
                      "text-xs px-2 py-1 rounded capitalize transition-colors " +
                      (filter === f
                        ? "bg-white shadow-sm heading dark:bg-zinc-950"
                        : "muted hover:text-zinc-900 dark:hover:text-zinc-100")
                    }
                  >
                    {f}
                  </button>
                ))}
              </div>
              <button onClick={load} disabled={loading} className="btn-ghost text-xs py-1.5 px-2" title="Refresh">
                <RefreshCw className={"h-3.5 w-3.5 " + (loading ? "animate-spin" : "")} />
              </button>
            </div>
          </div>

          <div className="sm:hidden px-3 pt-3">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 muted" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search…"
                aria-label="Search containers"
                className="input pl-8 py-1.5 text-sm w-full"
              />
            </div>
            <div className="flex gap-1 mt-2 overflow-x-auto">
              {(["all", "running", "stopped", "managed"] as FilterKind[]).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={
                    "text-xs px-2.5 py-1 rounded-full capitalize whitespace-nowrap " +
                    (filter === f ? "bg-zinc-900 text-white dark:bg-white dark:text-zinc-900" : "bg-zinc-100 dark:bg-zinc-800 muted")
                  }
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="m-3 tone-failed text-sm rounded p-2 border-l-2 border-current">{error}</div>
          )}

          {filtered.length === 0 ? (
            <div className="py-12 text-center">
              <Boxes className="h-6 w-6 muted mx-auto mb-2" />
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
                  <tr className="text-left text-xs font-medium muted border-b border-zinc-200 dark:border-zinc-800">
                    <th className="py-2 pl-4 pr-3 font-medium">Name</th>
                    <th className="py-2 pr-3 font-medium">ID</th>
                    <th className="py-2 pr-3 font-medium">Image</th>
                    <th className="py-2 pr-3 font-medium">Status</th>
                    <th className="py-2 pr-3 font-medium">Ports</th>
                    <th className="py-2 pr-4 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                  {filtered.map((c) => {
                    const shortId = c.id.slice(0, 12);
                    const running = (c.status || "").toLowerCase().includes("running");
                    const isBusy = busyId === c.id;
                    return (
                      <tr key={c.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-900/60 transition-colors">
                        <td className="py-2 pl-4 pr-3">
                          <div className="flex items-center gap-2 min-w-0">
                            <Circle
                              className={"h-2 w-2 shrink-0 " + (running ? "fill-emerald-500 text-emerald-500" : "fill-zinc-400 text-zinc-400")}
                            />
                            <div className="min-w-0">
                              <div className="font-medium heading truncate max-w-[11rem]">
                                {c.name || "(unnamed)"}
                              </div>
                              {c.managed && (
                                <div className="text-[10px] muted mt-0.5 inline-flex items-center gap-1">
                                  <ShieldCheck className="h-2.5 w-2.5" />
                                  managed by MCP
                                </div>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="py-2 pr-3">
                          <button
                            type="button"
                            onClick={() => copyId(c.id)}
                            className="group inline-flex items-center gap-1.5 font-mono text-xs px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors"
                            title={"Copy full ID: " + c.id}
                          >
                            {shortId}
                            <Copy className="h-3 w-3 opacity-50 group-hover:opacity-100" />
                          </button>
                        </td>
                        <td className="py-2 pr-3 font-mono text-xs truncate max-w-[13rem] muted">
                          {c.image || "—"}
                        </td>
                        <td className="py-2 pr-3">
                          <span className={"badge " + statusTone(c.status)}>{c.status || "unknown"}</span>
                        </td>
                        <td className="py-2 pr-3 text-xs muted max-w-[11rem] truncate">
                          {formatPorts(c.ports)}
                        </td>
                        <td className="py-2 pr-4">
                          <div className="flex items-center justify-end gap-1">
                            {canMutate && running && (
                              <button
                                type="button"
                                onClick={() => setConfirmAction({ kind: "stop", container: c })}
                                disabled={isBusy}
                                className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded tone-pending hover:bg-amber-50 dark:hover:bg-amber-500/10 disabled:opacity-50"
                                title="Stop container"
                              >
                                <Square className="h-3 w-3" />
                                Stop
                              </button>
                            )}
                            {canMutate && (
                              <button
                                type="button"
                                onClick={() => setConfirmAction({ kind: "remove", container: c })}
                                disabled={isBusy}
                                className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded tone-failed hover:bg-red-50 dark:hover:bg-red-500/10 disabled:opacity-50"
                                title="Remove container"
                              >
                                <Trash2 className="h-3 w-3" />
                                Remove
                              </button>
                            )}
                            {!canMutate && <span className="text-[10px] muted italic">read-only</span>}
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
            <div className="px-4 py-2.5 border-t border-zinc-200 dark:border-zinc-800 text-xs muted flex items-center justify-between flex-wrap gap-2">
              <span>
                Showing {filtered.length} of {containers.length}
              </span>
              <span>Auto-refresh every 10s</span>
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={!!confirmAction}
        busy={busyId !== null}
        title={confirmAction?.kind === "stop" ? "Stop this container?" : "Remove this container?"}
        message={
          confirmAction ? (
            <div className="space-y-2">
              <p>
                {confirmAction.kind === "stop"
                  ? "This will send a SIGTERM to the container and wait for it to stop gracefully."
                  : "This will permanently remove the container. Its data will be lost unless it was persisted to a volume."}
              </p>
              <div className="rounded bg-zinc-50 dark:bg-zinc-800/60 p-2 text-xs font-mono">
                <div>
                  <span className="muted">ID: </span>
                  {confirmAction.container.id.slice(0, 24)}
                </div>
                <div>
                  <span className="muted">Name: </span>
                  {confirmAction.container.name || "(unnamed)"}
                </div>
                <div>
                  <span className="muted">Image: </span>
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
