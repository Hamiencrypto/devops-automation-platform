"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  User as UserIcon,
  Shield,
  Wrench,
  UserCircle2,
  Moon,
  Sun,
  Monitor,
  LogOut,
  Info,
  CheckCircle2,
  Server,
  KeyRound,
} from "lucide-react";
import DashboardShell from "@/components/layout/DashboardShell";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { useToast } from "@/components/ui/Toast";
import { fetchHealth, API_BASE_URL } from "@/lib/api";

function roleIcon(role?: string) {
  if (role === "admin") return <Shield className="h-3.5 w-3.5 text-zinc-500" />;
  if (role === "developer") return <Wrench className="h-3.5 w-3.5 text-zinc-500" />;
  return <UserCircle2 className="h-3.5 w-3.5 text-zinc-500" />;
}

function ThemeButton({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ElementType;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={
        "flex flex-col items-center gap-1.5 p-3 rounded-lg border transition-colors " +
        (active
          ? "border-violet-400 bg-violet-500/10 heading dark:border-violet-500/60"
          : "border-black/10 hover:border-black/20 muted dark:border-white/10 dark:hover:border-white/20")
      }
    >
      <Icon className="h-4 w-4" />
      <span className="text-xs font-medium">{label}</span>
    </button>
  );
}

export default function SettingsPage() {
  const router = useRouter();
  const { user, authEnabled, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const { push } = useToast();
  const [health, setHealth] = useState<{
    status: string;
    version: string;
    checks: Record<string, string>;
  } | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  return (
    <DashboardShell title="Settings">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Profile */}
        <div className="card p-5 lg:col-span-2">
          <div className="flex items-center gap-1.5 mb-3">
            <UserIcon className="h-4 w-4 text-zinc-400" />
            <h2 className="text-sm font-semibold heading">Profile</h2>
          </div>

          {!authEnabled && (
            <div className="tone-pending text-sm rounded-md border-l-2 border-current pl-3 py-1.5 mb-4">
              Authentication is disabled on the backend. All requests run as anonymous. Enable it
              by setting <code className="font-mono">ENABLE_AUTH=true</code>.
            </div>
          )}

          {user ? (
            <div className="flex items-center gap-3">
              <div className="h-12 w-12 rounded-full bg-gradient-brand text-white flex items-center justify-center text-base font-semibold">
                {user.username.slice(0, 2).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-base font-semibold heading">{user.username}</div>
                <div className="text-sm muted truncate">{user.email}</div>
                <div className="mt-1 inline-flex items-center gap-1 text-xs">
                  {roleIcon(user.role)}
                  <span className="capitalize heading">{user.role}</span>
                  {user.is_active && (
                    <span className="ml-1 inline-flex items-center gap-1 tone-success">
                      <CheckCircle2 className="h-3 w-3" />
                      active
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={() => {
                  logout();
                  push("Signed out", "info", 2000);
                  router.replace("/login");
                }}
                className="btn-secondary"
              >
                <LogOut className="h-3.5 w-3.5" />
                Sign out
              </button>
            </div>
          ) : (
            <div className="text-sm muted">You are not signed in.</div>
          )}

          {user && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 mt-5">
              <InfoBox label="Username" value={user.username} />
              <InfoBox label="Email" value={user.email} />
              <InfoBox label="Member since" value={new Date(user.created_at).toLocaleDateString()} />
            </div>
          )}
        </div>

        {/* Theme */}
        <div className="card p-5">
          <div className="flex items-center gap-1.5 mb-3">
            <Monitor className="h-4 w-4 text-zinc-400" />
            <h2 className="text-sm font-semibold heading">Appearance</h2>
          </div>
          <p className="text-sm muted mb-3">Your preference is saved locally.</p>
          <div className="grid grid-cols-2 gap-2.5">
            <ThemeButton active={theme === "light"} onClick={() => setTheme("light")} icon={Sun} label="Light" />
            <ThemeButton active={theme === "dark"} onClick={() => setTheme("dark")} icon={Moon} label="Dark" />
          </div>
        </div>

        {/* System */}
        <div className="card p-5 lg:col-span-2">
          <div className="flex items-center gap-1.5 mb-3">
            <Server className="h-4 w-4 text-zinc-400" />
            <h2 className="text-sm font-semibold heading">System</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            <InfoBox label="API endpoint" value={API_BASE_URL} mono />
            <InfoBox label="Version" value={health?.version || "unknown"} mono />
            <InfoBox label="Backend status" value={health?.status || "unknown"} />
            <InfoBox label="Auth mode" value={authEnabled ? "enabled" : "disabled"} />
          </div>
          {health?.checks && Object.keys(health.checks).length > 0 && (
            <div className="mt-3.5">
              <p className="label-caps mb-1.5">Service checks</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {Object.entries(health.checks).map(([k, v]) => {
                  // "ok"/"healthy" are real up/down checks; a bare number
                  // (tools_loaded: "5") is an informational count, not a
                  // failure — only treat it as broken if it's neither.
                  const ok = v === "ok" || v === "healthy";
                  const isCount = /^\d+$/.test(v);
                  const badgeClass = ok ? "badge-success" : isCount ? "badge-neutral" : "badge-failed";
                  return (
                    <div
                      key={k}
                      className="flex items-center justify-between gap-2 rounded-md px-2.5 py-1.5 bg-black/5 dark:bg-white/5 text-sm"
                    >
                      <span className="muted shrink-0">{k}</span>
                      <span
                        className={"badge min-w-0 max-w-[70%] truncate " + badgeClass}
                        title={v}
                      >
                        {v}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Security / About */}
        <div className="card p-5 space-y-4">
          <div>
            <div className="flex items-center gap-1.5 mb-1.5">
              <KeyRound className="h-4 w-4 text-zinc-400" />
              <h2 className="text-sm font-semibold heading">Security</h2>
            </div>
            <p className="text-sm muted">
              Sessions are authenticated with JWT tokens stored in your browser. Signing out
              removes the token from this device.
            </p>
          </div>
          <div className="pt-3.5 border-t border-black/5 dark:border-white/10">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Info className="h-4 w-4 text-zinc-400" />
              <h2 className="text-sm font-semibold heading">About</h2>
            </div>
            <p className="text-sm muted leading-relaxed">
              <strong className="heading">AI-Powered DevOps Automation Platform</strong>
              <br />
              Final Year Project · University of Sindh
              <br />
              Department of Information Technology · 2025-2026
            </p>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}

function InfoBox({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-md bg-black/5 dark:bg-white/5 p-2.5">
      <p className="label-caps">{label}</p>
      <p className={"mt-1 text-sm heading break-all " + (mono ? "font-mono" : "")}>{value}</p>
    </div>
  );
}
