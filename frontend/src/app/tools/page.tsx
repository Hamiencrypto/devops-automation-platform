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
      <div className="space-y-4">
        <div className="card p-4 flex flex-col md:flex-row md:items-center gap-3 justify-between">
          <div>
            <h2 className="text-sm font-semibold heading">Model Context Protocol catalog</h2>
            <p className="text-xs muted mt-0.5">
              {tools.length} tool{tools.length === 1 ? "" : "s"} registered and routable by natural language.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 muted" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search tools or intents…"
                aria-label="Search tools"
                className="input pl-8 py-1.5 text-sm w-56"
              />
            </div>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              aria-label="Filter by category"
              className="input py-1.5 text-sm w-32 capitalize"
            >
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        </div>

        {error && <div className="card p-3 tone-failed text-sm">{error}</div>}
        {loading && <div className="card p-8 text-center muted text-sm">Loading tool catalog…</div>}
        {!loading && filtered.length === 0 && (
          <div className="card p-8 text-center muted text-sm">No tools match your filters.</div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {filtered.map((tool) => {
            const Icon = CATEGORY_ICON[tool.category] || Wrench;
            const isOpen = !!expanded[tool.name];
            return (
              <div key={tool.name} className="card">
                <button
                  type="button"
                  onClick={() => setExpanded((prev) => ({ ...prev, [tool.name]: !prev[tool.name] }))}
                  aria-expanded={isOpen}
                  className="w-full text-left p-4 flex items-start gap-3"
                >
                  <div className="h-9 w-9 rounded-md bg-zinc-100 text-zinc-600 flex items-center justify-center shrink-0 dark:bg-zinc-800 dark:text-zinc-300">
                    <Icon className="h-4.5 w-4.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-mono text-sm font-semibold heading">{tool.name}</h3>
                      <span className="chip text-[10px] capitalize">{tool.category}</span>
                      {tool.destructive && (
                        <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded tone-failed bg-red-50 dark:bg-red-500/10">
                          <AlertTriangle className="h-2.5 w-2.5" />
                          destructive
                        </span>
                      )}
                    </div>
                    <p className="text-sm muted mt-1">{tool.description}</p>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {tool.intents.map((i) => (
                        <span key={i} className="chip text-[10px] inline-flex items-center gap-1">
                          <Hash className="h-2.5 w-2.5" />
                          {i}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="muted pt-1 shrink-0">
                    {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  </div>
                </button>

                {isOpen && (
                  <div className="border-t border-zinc-200 dark:border-zinc-800 p-4 pt-3 space-y-2">
                    <p className="label-caps">Input schema</p>
                    <pre className="json-viewer max-h-80">{JSON.stringify(tool.input_schema, null, 2)}</pre>
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
