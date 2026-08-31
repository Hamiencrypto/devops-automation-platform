"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Wrench,
  Container as ContainerIcon,
  FileText,
  FileSearch,
  Server,
  Cloud,
  Search,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Hash,
} from "lucide-react";
import DashboardShell from "@/components/layout/DashboardShell";
import { fetchTools, type ToolSchema } from "@/lib/api";

const CATEGORY_ICON: Record<string, React.ElementType> = {
  docker: ContainerIcon,
  logs: FileSearch,
  file: FileText,
  system: Server,
  kubernetes: Cloud,
  general: Wrench,
};

export default function ToolsPage() {
  const [tools, setTools] = useState<ToolSchema[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string>("all");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetchTools()
      .then((res) => setTools(res.tools))
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, []);

  const categories = useMemo(() => {
    const set = new Set<string>();
    tools.forEach((t) => set.add(t.category));
    return ["all", ...Array.from(set).sort()];
  }, [tools]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tools.filter((t) => {
      if (category !== "all" && t.category !== category) return false;
      if (!q) return true;
      return (
        t.name.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q) ||
        t.intents.some((i) => i.toLowerCase().includes(q))
      );
    });
  }, [tools, query, category]);

  return (
    <DashboardShell title="MCP Tools">
      <div className="space-y-5">
        <div
          className="card p-5 flex flex-col md:flex-row md:items-center gap-4 justify-between
                     bg-gradient-to-br from-brand-50 to-white border-brand-200/60
                     dark:from-brand-500/10 dark:to-transparent dark:border-brand-500/20"
        >
          <div className="flex items-start gap-3">
            <div className="h-10 w-10 rounded-xl bg-brand-500 text-white flex items-center justify-center shadow-glow">
              <Wrench className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-semibold heading text-lg">Model Context Protocol Catalog</h2>
              <p className="text-sm muted mt-0.5">
                {tools.length} tool{tools.length === 1 ? "" : "s"} registered and routable by natural language.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 muted" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search tools or intents…"
                className="input pl-9 py-2 text-sm w-60"
              />
            </div>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="input py-2 text-sm w-36 capitalize"
            >
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        </div>

        {error && (
          <div className="card p-4 text-sm text-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        {loading && (
          <div className="card p-10 text-center muted text-sm">
            Loading tool catalog…
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <div className="card p-10 text-center muted text-sm">
            No tools match your filters.
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filtered.map((tool) => {
            const Icon = CATEGORY_ICON[tool.category] || Wrench;
            const isOpen = !!expanded[tool.name];
            return (
              <div key={tool.name} className="card">
                <button
                  type="button"
                  onClick={() =>
                    setExpanded((prev) => ({ ...prev, [tool.name]: !prev[tool.name] }))
                  }
                  className="w-full text-left p-5 flex items-start gap-3"
                >
                  <div
                    className="h-11 w-11 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center shrink-0
                               dark:bg-brand-500/10 dark:text-brand-300"
                  >
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-mono text-sm font-semibold heading">
                        {tool.name}
                      </h3>
                      <span className="chip text-[10px] capitalize">{tool.category}</span>
                      {tool.destructive && (
                        <span
                          className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded
                                     bg-red-100 text-red-700
                                     dark:bg-red-500/15 dark:text-red-300"
                        >
                          <AlertTriangle className="h-2.5 w-2.5" />
                          destructive
                        </span>
                      )}
                    </div>
                    <p className="text-sm muted mt-1">{tool.description}</p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {tool.intents.map((i) => (
                        <span key={i} className="chip text-[10px] inline-flex items-center gap-1">
                          <Hash className="h-2.5 w-2.5" />
                          {i}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="muted pt-1 shrink-0">
                    {isOpen ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </div>
                </button>

                {isOpen && (
                  <div className="border-t border-slate-200 dark:border-slate-800 p-5 pt-4 space-y-2">
                    <p className="text-xs font-medium uppercase muted tracking-wider">
                      Input schema
                    </p>
                    <pre className="json-viewer max-h-80">
                      {JSON.stringify(tool.input_schema, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </DashboardShell>
  );
}
