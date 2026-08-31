"use client";

import { useEffect, useState } from "react";
import { Activity } from "lucide-react";
import { fetchHealth, API_BASE_URL } from "@/lib/api";

type HealthState = {
  status: string;
  version: string;
  checks: Record<string, string>;
  errorDetail?: string;
};

export default function HealthBadge() {
  const [health, setHealth] = useState<HealthState | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = () => {
      fetchHealth()
        .then((h) => !cancelled && setHealth(h))
        .catch((err) => {
          if (cancelled) return;
          setHealth({
            status: "offline",
            version: "?",
            checks: { api: "unreachable" },
            errorDetail:
              (err instanceof Error ? err.message : String(err)) +
              ` (target: ${API_BASE_URL})`,
          });
        });
    };
    poll();
    const t = setInterval(poll, 8000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  if (!health) return null;

  const color =
    health.status === "ok"
      ? "bg-emerald-100 text-emerald-700 border-emerald-200"
      : health.status === "degraded"
        ? "bg-amber-100 text-amber-700 border-amber-200"
        : "bg-red-100 text-red-700 border-red-200";

  const tooltip =
    health.errorDetail ||
    Object.entries(health.checks)
      .map(([k, v]) => `${k}: ${v}`)
      .join("\n");

  return (
    <span
      className={"badge border " + color}
      title={tooltip}
      style={{ cursor: "help" }}
    >
      <Activity className="h-3 w-3" />
      {health.status} · v{health.version}
    </span>
  );
}
