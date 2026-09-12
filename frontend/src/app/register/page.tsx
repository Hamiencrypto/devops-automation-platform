"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ShieldCheck, Loader2, Moon, Sun, AlertCircle } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";

export default function RegisterPage() {
  const router = useRouter();
  const { register, user, authEnabled, loading } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!authEnabled || user) router.replace("/");
  }, [loading, authEnabled, user, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setSubmitting(true);
    try {
      await register({ username: username.trim(), email: email.trim(), password });
      router.replace("/");
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
          <h1 className="text-xl font-semibold heading">Create your account</h1>
          <p className="text-sm muted mt-1">The first account becomes the administrator</p>
        </div>

        <div className="card p-5">
          <form onSubmit={handleSubmit} className="space-y-3.5">
            <div>
              <label htmlFor="reg-username" className="block text-sm font-medium heading mb-1.5">
                Username
              </label>
              <input
                id="reg-username"
                type="text"
                required
                minLength={3}
                maxLength={64}
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input"
                placeholder="hamza"
              />
            </div>
            <div>
              <label htmlFor="reg-email" className="block text-sm font-medium heading mb-1.5">
                Email
              </label>
              <input
                id="reg-email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input"
                placeholder="you@university.edu"
              />
            </div>
            <div>
              <label htmlFor="reg-password" className="block text-sm font-medium heading mb-1.5">
                Password
              </label>
              <input
                id="reg-password"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                placeholder="At least 8 characters"
              />
            </div>
            <div>
              <label htmlFor="reg-confirm" className="block text-sm font-medium heading mb-1.5">
                Confirm password
              </label>
              <input
                id="reg-confirm"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="input"
              />
            </div>

            {error && (
              <div className="tone-failed text-sm rounded-md border-l-2 border-current pl-3 py-1.5 flex items-start gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <button type="submit" disabled={submitting} className="btn-primary w-full">
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Create account"}
            </button>
          </form>

          <div className="mt-5 text-center text-sm muted">
            Already have an account?{" "}
            <Link href="/login" className="font-medium heading hover:underline">
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
