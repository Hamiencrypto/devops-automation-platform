"use client";

import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import { useRequireAuth } from "@/lib/auth";
import { Loader2 } from "lucide-react";

export default function DashboardShell({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const { user, loading, authEnabled } = useRequireAuth();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-3 muted">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-sm">Loading…</span>
        </div>
      </div>
    );
  }

  if (authEnabled && !user) {
    // useRequireAuth will redirect — render nothing in the meantime
    return null;
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 min-w-0">
        <TopBar title={title} />
        <main className="p-5 max-w-screen-2xl mx-auto">{children}</main>
      </div>
    </div>
  );
}
