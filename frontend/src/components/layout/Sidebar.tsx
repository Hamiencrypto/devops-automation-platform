"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Boxes,
  Terminal,
  Wrench,
  ScrollText,
  Radio,
  Settings,
  Cpu,
} from "lucide-react";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/containers", label: "Containers", icon: Boxes },
  { href: "/commands", label: "Commands", icon: Terminal },
  { href: "/tools", label: "MCP Tools", icon: Wrench },
  { href: "/history", label: "History", icon: ScrollText },
  { href: "/logs", label: "Live Logs", icon: Radio },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      className="hidden lg:flex w-64 shrink-0 flex-col border-r border-slate-200
                 dark:border-slate-800 bg-white dark:bg-[#0b1220]
                 sticky top-0 h-screen"
    >
      <div className="px-5 py-5 border-b border-slate-200 dark:border-slate-800">
        <Link href="/" className="flex items-center gap-3">
          <div
            className="h-10 w-10 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700
                       text-white flex items-center justify-center shadow-glow"
          >
            <Cpu className="h-5 w-5" />
          </div>
          <div>
            <div className="text-sm font-semibold heading">DevOps MCP</div>
            <div className="text-xs muted">Automation Platform</div>
          </div>
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={"sidebar-link " + (active ? "active" : "")}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="px-5 py-4 border-t border-slate-200 dark:border-slate-800 text-xs muted">
        <div className="font-medium heading mb-1">FYP 2025–2026</div>
        University of Sindh
        <br />
        Dept. of Information Technology
      </div>
    </aside>
  );
}
