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
    return (
      <div className="card p-6 text-sm muted text-center">
        Loading registered tools…
      </div>
    );
  }

  if (tools.length === 0) {
    return (
      <div className="card p-6 text-sm muted text-center">
        No MCP tools registered yet.
      </div>
    );
  }

  const display = compact ? tools.slice(0, 6) : tools;

  return (
    <div className="card">
      {showTitle && (
        <div className="card-header">
          <div className="card-title">
            <Wrench className="h-4 w-4" />
            Registered MCP Tools
            <span className="chip ml-1">{tools.length}</span>
          </div>
        </div>
      )}

      <div className={"grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 " + (showTitle ? "p-4" : "")}>
        {display.map((tool) => {
          const Icon = CATEGORY_ICON[tool.category] || Wrench;
          return (
            <div
              key={tool.name}
              className="group rounded-xl border border-slate-200 p-4 hover:border-brand-400 hover:shadow-md
                         transition bg-white
                         dark:bg-slate-900/40 dark:border-slate-800 dark:hover:border-brand-500/40"
            >
              <div className="flex items-start gap-3">
                <div
                  className="h-10 w-10 rounded-lg bg-brand-50 text-brand-600
                             flex items-center justify-center shrink-0 group-hover:bg-brand-100
                             dark:bg-brand-500/10 dark:text-brand-300 dark:group-hover:bg-brand-500/20"
                >
                  <Icon className="h-5 w-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-mono text-sm font-semibold heading truncate">
                      {tool.name}
                    </p>
                    {tool.destructive && (
                      <span
                        className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded
                                   bg-red-100 text-red-700
                                   dark:bg-red-500/15 dark:text-red-300"
                        title="This tool can modify or destroy state"
                      >
                        <AlertTriangle className="h-2.5 w-2.5" />
                        destructive
                      </span>
                    )}
                  </div>
                  <p className="text-xs muted mt-1 line-clamp-2">{tool.description}</p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {tool.intents.slice(0, 3).map((i) => (
                      <span key={i} className="chip text-[10px]">
                        {i}
                      </span>
                    ))}
                    {tool.intents.length > 3 && (
                      <span className="chip text-[10px]">
                        +{tool.intents.length - 3}
                      </span>
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
