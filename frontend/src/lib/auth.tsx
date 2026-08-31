"use client";

/**
 * Auth context — wraps the app, exposes login/register/logout and the
 * current user. Drives protected routing via useRequireAuth().
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useRouter, usePathname } from "next/navigation";
import {
  fetchMe,
  getToken,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  setToken,
  type User,
  type UserRole,
} from "@/lib/api";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  authEnabled: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (payload: {
    username: string;
    email: string;
    password: string;
    role?: UserRole;
  }) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [authEnabled, setAuthEnabled] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const me = await fetchMe();
      setUser(me);
      setAuthEnabled(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      // If backend has auth disabled it returns a specific sentinel
      if (msg.toLowerCase().includes("auth disabled")) {
        setAuthEnabled(false);
        setUser(null);
      } else {
        setUser(null);
        setToken(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const hasToken = !!getToken();
    if (hasToken) {
      refresh();
    } else {
      // Probe /auth/me anyway so we can detect ENABLE_AUTH=false
      refresh();
    }
  }, [refresh]);

  const login = useCallback(
    async (username: string, password: string) => {
      await apiLogin(username, password);
      await refresh();
    },
    [refresh]
  );

  const register = useCallback(
    async (payload: {
      username: string;
      email: string;
      password: string;
      role?: UserRole;
    }) => {
      await apiRegister(payload);
      await apiLogin(payload.username, payload.password);
      await refresh();
    },
    [refresh]
  );

  const logout = useCallback(() => {
    apiLogout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, loading, authEnabled, login, register, logout, refresh }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

/** Redirect to /login if the user isn't authenticated (and auth is on). */
export function useRequireAuth() {
  const { user, loading, authEnabled } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading) return;
    if (!authEnabled) return;
    if (!user) {
      const qs = new URLSearchParams({ next: pathname || "/" }).toString();
      router.replace(`/login?${qs}`);
    }
  }, [user, loading, authEnabled, pathname, router]);

  return { user, loading, authEnabled };
}
