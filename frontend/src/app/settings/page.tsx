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
  if (role === "admin") return <Shield className="h-4 w-4 text-brand-500" />;
  if (role === "developer") return <Wrench className="h-4 w-4 text-emerald-500" />;
  return <UserCircle2 className="h-4 w-4 text-slate-500" />;
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
      className={
        "flex flex-col items-center gap-2 p-4 rounded-xl border transition " +
        (active
          ? "border-brand-500 bg-brand-50 text-brand-700 shadow-sm dark:bg-brand-500/10 dark:text-brand-300"
          : "border-slate-200 hover:border-slate-300 muted dark:border-slate-800 dark:hover:border-slate-700")
      }
    >
      <Icon className="h-5 w-5" />
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
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Profile */}
        <div className="card p-6 lg:col-span-2">
          <div className="flex items-center gap-2 mb-4">
            <UserIcon className="h-4 w-4 text-brand-500" />
            <h2 className="font-semibold heading">Profile</h2>
          </div>

          {!authEnabled && (
            <div className="rounded-lg bg-amber-50 ring-1 ring-amber-200 p-3 text-sm text-amber-800
                            dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/20 mb-4">
              Authentication is disabled on the backend. All requests run as anonymous.
              Enable it by setting <code className="font-mono">ENABLE_AUTH=true</code>.
            </div>
          )}

          {user ? (
            <div className="flex items-center gap-4">
              <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-brand-400 to-brand-600 text-white flex items-center justify-center text-xl font-bold shadow-glow">
                {user.username.slice(0, 2).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-lg font-semibold heading">{user.username}</div>
                <div className="text-sm muted truncate">{user.email}</div>
                <div className="mt-1 inline-flex items-center gap-1 text-xs">
                  {roleIcon(user.role)}
                  <span className="capitalize heading">{user.role}</span>
                  {user.is_active && (
                    <span className="ml-1 inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
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
                <LogOut className="h-4 w-4" />
                Sign out
              </button>
            </div>
          ) : (
            <div className="text-sm muted">You are not signed in.</div>
          )}

          {user && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-6">
              <InfoBox label="Username" value={user.username} />
              <InfoBox label="Email" value={user.email} />
              <InfoBox
                label="Member since"
                value={new Date(user.created_at).toLocaleDateString()}
              />
            </div>
          )}
        </div>

        {/* Theme */}
        <div className="card p-6">
          <div className="flex items-center gap-2 mb-4">
            <Monitor className="h-4 w-4 text-brand-500" />
            <h2 className="font-semibold heading">Appearance</h2>
          </div>
          <p className="text-sm muted mb-4">
            Choose a theme. Your preference is saved locally.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <ThemeButton
              active={theme === "light"}
              onClick={() => setTheme("light")}
              icon={Sun}
              label="Light"
            />
            <ThemeButton
              active={theme === "dark"}
              onClick={() => setTheme("dark")}
              icon={Moon}
              label="Dark"
            />
          </div>
        </div>

        {/* System */}
        <div className="card p-6 lg:col-span-2">
          <div className="flex items-center gap-2 mb-4">
            <Server className="h-4 w-4 text-brand-500" />
            <h2 className="font-semibold heading">System</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <InfoBox label="API endpoint" value={API_BASE_URL} mono />
            <InfoBox label="Version" value={health?.version || "unknown"} mono />
            <InfoBox label="Backend status" value={health?.status || "unknown"} />
            <InfoBox
              label="Auth mode"
              value={authEnabled ? "enabled" : "disabled"}
            />
          </div>
          {health?.checks && Object.keys(health.checks).length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-medium uppercase muted tracking-wider mb-2">
                Service checks
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {Object.entries(health.checks).map(([k, v]) => {
                  const ok = v === "ok" || v === "healthy";
                  return (
                    <div
                      key={k}
                      className="flex items-center justify-between rounded-lg px-3 py-2
                                 bg-slate-50 dark:bg-slate-800/60 text-sm"
                    >
                      <span className="muted">{k}</span>
                      <span
                        className={
                          "badge " +
                          (ok
                            ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300"
                            : "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300")
                        }
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
        <div className="card p-6 space-y-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <KeyRound className="h-4 w-4 text-brand-500" />
              <h2 className="font-semibold heading">Security</h2>
            </div>
            <p className="text-sm muted">
              Sessions are authenticated with JWT tokens stored in your browser. Signing out
              removes the token from this device.
            </p>
          </div>
          <div className="pt-4 border-t border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-2 mb-2">
              <Info className="h-4 w-4 text-brand-500" />
              <h2 className="font-semibold heading">About</h2>
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

function InfoBox({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/60">
      <p className="text-[10px] uppercase font-medium muted tracking-wider">{label}</p>
      <p
        className={
          "mt-1 text-sm heading break-all " + (mono ? "font-mono" : "")
        }
      >
        {value}
      </p>
    </div>
  );
}
