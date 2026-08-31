"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Radio,
  Play,
  Square,
  Trash2,
  Download,
  Link as LinkIcon,
  CircleOff,
  Copy,
} from "lucide-react";
import DashboardShell from "@/components/layout/DashboardShell";
import { useToast } from "@/components/ui/Toast";
import { fetchContainers, API_BASE_URL, type ContainerInfo } from "@/lib/api";

interface LogLine {
  id: number;
  text: string;
  ts: string;
  kind: "log" | "info" | "error";
}

function toWsBase(): string {
  const override = process.env.NEXT_PUBLIC_WS_URL;
  if (override && !override.includes("backend:")) return override.replace(/\/+$/, "");
  try {
    const u = new URL(API_BASE_URL);
    return `${u.protocol === "https:" ? "wss:" : "ws:"}//${u.host}`;
  } catch {
    return "ws://localhost:8000";
  }
}

export default function LogsPage() {
  const { push } = useToast();
  const [containers, setContainers] = useState<ContainerInfo[]>([]);
  const [target, setTarget] = useState("");
  const [custom, setCustom] = useState("");
  const [status, setStatus] = useState<"idle" | "connecting" | "open" | "closed" | "error">("idle");
  const [lines, setLines] = useState<LogLine[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);
  const idRef = useRef(1);
  const scrollerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchContainers()
      .then((r) => setContainers(r.containers))
      .catch(() => setContainers([]));
  }, []);

  useEffect(() => {
    if (autoScroll && scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
    }
  }, [lines, autoScroll]);

  const append = useCallback((text: string, kind: LogLine["kind"] = "log") => {
    setLines((prev) => {
      const next = [
        ...prev,
        {
          id: idRef.current++,
          text,
          ts: new Date().toLocaleTimeString(),
          kind,
        },
      ];
      // Cap at 2000 lines to avoid memory runaway
      return next.length > 2000 ? next.slice(next.length - 2000) : next;
    });
  }, []);

  function disconnect() {
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus("closed");
  }

  function connect() {
    const name = (target || custom).trim();
    if (!name) {
      push("Pick a container or enter an ID", "warn");
      return;
    }
    disconnect();
    const url = `${toWsBase()}/ws/logs/${encodeURIComponent(name)}`;
    setStatus("connecting");
    append(`Connecting to ${name}…`, "info");
    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;
      ws.onopen = () => {
        setStatus("open");
        append(`Connected. Streaming logs for ${name}`, "info");
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data?.error) {
            append(`ERROR: ${data.error}`, "error");
            return;
          }
          if (data?.event === "subscribed") {
            append(`Subscribed to container: ${data.container || name}`, "info");
            return;
          }
          if (typeof data?.line === "string") {
            append(data.line, "log");
          } else if (typeof data === "string") {
            append(data, "log");
          } else {
            append(JSON.stringify(data), "log");
          }
        } catch {
          append(String(event.data), "log");
        }
      };
      ws.onerror = () => {
        setStatus("error");
        append("Socket error — check the container exists and the backend is reachable", "error");
      };
      ws.onclose = () => {
        setStatus("closed");
        append("Connection closed", "info");
      };
    } catch (e) {
      setStatus("error");
      append(`Failed to open socket: ${(e as Error).message}`, "error");
    }
  }

  useEffect(() => {
    return () => disconnect();
  }, []);

  function clearLog() {
    setLines([]);
  }

  function download() {
    const blob = new Blob(
      [lines.map((l) => `[${l.ts}] ${l.text}`).join("\n")],
      { type: "text/plain" }
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `logs-${(target || custom || "output").replace(/\W+/g, "_")}.log`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function copyAll() {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(lines.map((l) => l.text).join("\n"));
      push("Copied logs to clipboard", "info", 2000);
    }
  }

  const statusDot = {
    idle: "bg-slate-400",
    connecting: "bg-amber-400 animate-pulse",
    open: "bg-emerald-500 animate-pulse",
    closed: "bg-slate-500",
    error: "bg-red-500",
  }[status];

  return (
    <DashboardShell title="Live Logs">
      <div className="space-y-5">
        <div className="card p-5">
          <div className="flex flex-col md:flex-row md:items-end gap-3">
            <div className="flex-1 min-w-0">
              <label className="block text-xs font-medium uppercase muted tracking-wider mb-1.5">
                Select container
              </label>
              <select
                value={target}
                onChange={(e) => {
                  setTarget(e.target.value);
                  setCustom("");
                }}
                className="input w-full"
              >
                <option value="">— pick a running container —</option>
                {containers.map((c) => (
                  <option key={c.id} value={c.name || c.id}>
                    {(c.name || c.id.slice(0, 12)) + "  ·  " + c.image}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-1 min-w-0">
              <label className="block text-xs font-medium uppercase muted tracking-wider mb-1.5">
                Or container ID / name
              </label>
              <input
                value={custom}
                onChange={(e) => {
                  setCustom(e.target.value);
                  setTarget("");
                }}
                placeholder="e.g. abc123def456 or my-nginx"
                className="input w-full"
              />
            </div>
            <div className="flex items-center gap-2">
              {status === "open" || status === "connecting" ? (
                <button onClick={disconnect} className="btn-danger">
                  <Square className="h-4 w-4" />
                  Disconnect
                </button>
              ) : (
                <button onClick={connect} className="btn-primary">
                  <Play className="h-4 w-4" />
                  Stream
                </button>
              )}
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs muted">
            <span className={"h-2 w-2 rounded-full " + statusDot} />
            Status: <span className="heading">{status}</span>
            <span className="muted">·</span>
            <LinkIcon className="h-3 w-3" />
            <code className="font-mono">{toWsBase()}/ws/logs/…</code>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <Radio className="h-4 w-4" />
              Output
              <span className="chip ml-1">{lines.length} lines</span>
            </div>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-1.5 text-xs muted cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoScroll}
                  onChange={(e) => setAutoScroll(e.target.checked)}
                  className="accent-brand-500 rounded"
                />
                Follow tail
              </label>
              <button
                onClick={copyAll}
                className="btn-secondary text-xs py-1.5 px-3"
                disabled={lines.length === 0}
              >
                <Copy className="h-3.5 w-3.5" />
                Copy
              </button>
              <button
                onClick={download}
                className="btn-secondary text-xs py-1.5 px-3"
                disabled={lines.length === 0}
              >
                <Download className="h-3.5 w-3.5" />
                Download
              </button>
              <button
                onClick={clearLog}
                className="btn-secondary text-xs py-1.5 px-3"
                disabled={lines.length === 0}
              >
                <Trash2 className="h-3.5 w-3.5" />
                Clear
              </button>
            </div>
          </div>

          <div
            ref={scrollerRef}
            className="bg-slate-950 text-slate-100 font-mono text-xs p-4 h-[30rem] overflow-auto"
          >
            {lines.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-2 text-slate-500">
                <CircleOff className="h-5 w-5" />
                No logs yet. Pick a container and click Stream.
              </div>
            ) : (
              lines.map((l) => (
                <div
                  key={l.id}
                  className={
                    "whitespace-pre-wrap break-words " +
                    (l.kind === "error"
                      ? "text-red-400"
                      : l.kind === "info"
                        ? "text-brand-300"
                        : "text-green-300")
                  }
                >
                  <span className="text-slate-500">[{l.ts}] </span>
                  {l.text}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
