"use client";

import { useEffect, useState } from "react";
import {
  Wrench,
  Container as ContainerIcon,
  FileText,
  FileSearch,
  Server,
  Cloud,
  AlertTriangle,
} from "lucide-react";
import { fetchTools, type ToolSchema } from "@/lib/api";

const CATEGORY_ICON: Record<string, React.ElementType> = {
  docker: ContainerIcon,
  logs: FileSearch,
  file: FileText,
  system: Server,
  kubernetes: Cloud,
  general: Wrench,
};

export default function ToolsList({
  compact,
  showTitle = true,
}: {
  compact?: boolean;
  showTitle?: boolean;
}) {
  const [tools, setTools] = useState<ToolSchema[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTools()
      .then((res) => setTools(res.tools))
      .catch(() => setTools([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="card p-5 text-sm muted text-center">Loading registered tools…</div>;
  }

  if (tools.length === 0) {
    return <div className="card p-5 text-sm muted text-center">No MCP tools registered yet.</div>;
  }

  const display = compact ? tools.slice(0, 6) : tools;

  return (
    <div className="card">
      {showTitle && (
        <div className="card-header">
          <div className="card-title">
            <Wrench className="h-4 w-4" />
            Registered MCP tools
            <span className="chip ml-1">{tools.length}</span>
          </div>
        </div>
      )}

      <div className={"grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5 " + (showTitle ? "p-3" : "")}>
        {display.map((tool) => {
          const Icon = CATEGORY_ICON[tool.category] || Wrench;
          return (
            <div
              key={tool.name}
              className="rounded-xl border border-black/10 bg-white/40 backdrop-blur p-3 hover:border-violet-400/50 transition-colors
                         dark:border-white/10 dark:bg-white/[0.03] dark:hover:border-violet-500/40"
            >
              <div className="flex items-start gap-2.5">
                <div className="h-8 w-8 rounded-md bg-violet-500/10 text-violet-600 flex items-center justify-center shrink-0 dark:text-violet-400">
                  <Icon className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <p className="font-mono text-xs font-semibold heading truncate">{tool.name}</p>
                    {tool.destructive && (
                      <span
                        className="inline-flex items-center gap-1 text-[10px] px-1 py-0.5 rounded tone-failed bg-red-500/10"
                        title="This tool can modify or destroy state"
                      >
                        <AlertTriangle className="h-2.5 w-2.5" />
                        destructive
                      </span>
                    )}
                  </div>
                  <p className="text-xs muted mt-1 line-clamp-2">{tool.description}</p>
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {tool.intents.slice(0, 3).map((i) => (
                      <span key={i} className="chip text-[10px]">
                        {i}
                      </span>
                    ))}
                    {tool.intents.length > 3 && (
                      <span className="chip text-[10px]">+{tool.intents.length - 3}</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
