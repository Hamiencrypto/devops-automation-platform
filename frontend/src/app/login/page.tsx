"use client";

import { Suspense, useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ShieldCheck, Loader2, Moon, Sun, AlertCircle } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { login, user, authEnabled, loading } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const next = params.get("next") || "/";

  useEffect(() => {
    if (loading) return;
    if (!authEnabled || user) router.replace(next);
  }, [loading, authEnabled, user, router, next]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username.trim(), password);
      router.replace(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen auth-bg flex items-center justify-center p-4 relative">
      <button
        type="button"
        onClick={toggleTheme}
        className="absolute top-4 right-4 btn-ghost px-1.5"
        aria-label="Toggle theme"
      >
        {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>

      <div className="w-full max-w-sm">
        <div className="mb-7 text-center">
          <div className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 mb-4">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <h1 className="text-xl font-semibold heading">DevOps MCP Platform</h1>
          <p className="text-sm muted mt-1">Sign in to continue</p>
        </div>

        <div className="card p-5">
          <form onSubmit={handleSubmit} className="space-y-3.5">
            <div>
              <label htmlFor="username" className="block text-sm font-medium heading mb-1.5">
                Username
              </label>
              <input
                id="username"
                type="text"
                required
                autoFocus
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input"
                placeholder="admin"
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium heading mb-1.5">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div className="tone-failed text-sm rounded-md border-l-2 border-current pl-3 py-1.5 flex items-start gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <button type="submit" disabled={submitting} className="btn-primary w-full">
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Sign in"}
            </button>
          </form>

          <div className="mt-5 text-center text-sm muted">
            Don&apos;t have an account?{" "}
            <Link href="/register" className="font-medium heading hover:underline">
              Create one
            </Link>
          </div>
        </div>

        <p className="mt-6 text-center text-xs muted">
          University of Sindh · Department of Information Technology · FYP 2025–2026
        </p>
      </div>
    </div>
  );
}

function LoginFallback() {
  return (
    <div className="min-h-screen auth-bg flex items-center justify-center">
      <Loader2 className="h-5 w-5 animate-spin muted" />
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFallback />}>
      <LoginForm />
    </Suspense>
  );
}
