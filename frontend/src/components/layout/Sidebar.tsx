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
  ShieldCheck,
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
      className="hidden lg:flex w-56 shrink-0 flex-col border-r border-zinc-200
                 dark:border-zinc-800 bg-white dark:bg-canvas-dark
                 sticky top-0 h-screen"
    >
      <div className="px-4 py-4 border-b border-zinc-200 dark:border-zinc-800">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded-md bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 flex items-center justify-center">
            <ShieldCheck className="h-4 w-4" />
          </div>
          <div className="text-sm font-semibold heading leading-none">DevOps MCP</div>
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto px-2.5 py-3 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={"sidebar-link " + (active ? "active" : "")}
              aria-current={active ? "page" : undefined}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="px-4 py-3 border-t border-zinc-200 dark:border-zinc-800 text-xs muted">
        University of Sindh
        <br />
        Dept. of Information Technology
      </div>
    </aside>
  );
}
