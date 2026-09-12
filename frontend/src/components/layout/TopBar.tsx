"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Moon, Sun, LogOut, UserCircle2, Shield, Wrench } from "lucide-react";
import HealthBadge from "@/components/HealthBadge";
import { useTheme } from "@/lib/theme";
import { useAuth } from "@/lib/auth";

export default function TopBar({ title }: { title: string }) {
  const { theme, toggleTheme } = useTheme();
  const { user, authEnabled, logout } = useAuth();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const roleIcon =
    user?.role === "admin" ? (
      <Shield className="h-3 w-3" />
    ) : user?.role === "developer" ? (
      <Wrench className="h-3 w-3" />
    ) : (
      <UserCircle2 className="h-3 w-3" />
    );

  return (
    <header
      className="sticky top-0 z-20 flex h-12 items-center justify-between gap-4
                 border-b border-zinc-200 bg-white/90 px-5 backdrop-blur
                 dark:border-zinc-800 dark:bg-canvas-dark/90"
    >
      <h1 className="text-sm font-semibold heading">{title}</h1>

      <div className="flex items-center gap-2">
        <HealthBadge />

        <button
          type="button"
          onClick={toggleTheme}
          className="btn-ghost px-1.5"
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>

        {authEnabled && user ? (
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              className="flex items-center gap-2 rounded-md px-1.5 py-1
                         hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
            >
              <div className="h-6 w-6 rounded-full bg-zinc-200 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-200 flex items-center justify-center text-[10px] font-semibold">
                {user.username.slice(0, 2).toUpperCase()}
              </div>
              <div className="hidden md:block text-left">
                <div className="text-xs font-medium heading leading-tight">
                  {user.username}
                </div>
              </div>
            </button>

            {menuOpen && (
              <div
                role="menu"
                className="absolute right-0 mt-1.5 w-52 rounded-lg bg-white ring-1
                           ring-zinc-200 dark:bg-canvas-dark-raised dark:ring-zinc-800
                           overflow-hidden shadow-lg"
              >
                <div className="px-3 py-2.5 border-b border-zinc-200 dark:border-zinc-800">
                  <div className="text-sm font-medium heading">{user.username}</div>
                  <div className="text-xs muted flex items-center gap-1 mt-0.5">
                    {roleIcon}
                    {user.email}
                  </div>
                </div>
                <div className="py-1">
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setMenuOpen(false);
                      router.push("/settings");
                    }}
                    className="w-full flex items-center gap-2 px-3 py-1.5 text-sm
                               text-zinc-700 hover:bg-zinc-100
                               dark:text-zinc-200 dark:hover:bg-zinc-800"
                  >
                    <UserCircle2 className="h-3.5 w-3.5" />
                    Profile & settings
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      logout();
                      router.replace("/login");
                    }}
                    className="w-full flex items-center gap-2 px-3 py-1.5 text-sm tone-failed hover:bg-red-50 dark:hover:bg-red-500/10"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    Sign out
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </header>
  );
}
