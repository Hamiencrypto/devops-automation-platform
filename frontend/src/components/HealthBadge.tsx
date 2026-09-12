"use client";

import { useEffect, useState } from "react";
import { Circle } from "lucide-react";
import { fetchHealth, API_BASE_URL } from "@/lib/api";

type HealthState = {
  status: string;
  version: string;
  checks: Record<string, string>;
  errorDetail?: string;
};

const STATUS_CLASS: Record<string, string> = {
  ok: "badge-success",
  degraded: "badge-pending",
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

  const cls = STATUS_CLASS[health.status] || "badge-failed";
  const tooltip =
    health.errorDetail ||
    Object.entries(health.checks)
      .map(([k, v]) => `${k}: ${v}`)
      .join("\n");

  return (
    <span className={"badge " + cls} title={tooltip}>
      <Circle className="h-2 w-2 fill-current" />
      {health.status} · v{health.version}
    </span>
  );
}
