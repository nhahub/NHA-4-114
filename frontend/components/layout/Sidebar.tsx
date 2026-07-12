"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAlertsStore } from "@/lib/store";
import { logout } from "@/lib/auth";
import clsx from "clsx";

import {
  MonitorPlay,
  Bell,
  BarChart3,
  ScrollText,
  Video,
  Eye,
  Map,
  LogOut,
} from "lucide-react";

const navItems = [
  { href: "/monitor",   label: "Monitor",   icon: MonitorPlay },
  { href: "/alerts",    label: "Alerts",    icon: Bell        },
  { href: "/analytics", label: "Analytics", icon: BarChart3   },
  { href: "/logs",      label: "Logs",      icon: ScrollText  },
  { href: "/cameras",   label: "Cameras",   icon: Video       },
  { href: "/zones",     label: "Zones",     icon: Map         },
];

export default function Sidebar() {
  const pathname = usePathname();
  const liveAlerts = useAlertsStore((s) => s.liveAlerts);
  const highCount = liveAlerts.filter((a) => a.severity === "high").length;

  return (
    <aside className="w-56 bg-surface-800 border-r border-border flex flex-col shrink-0">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded bg-accent/10 border border-accent/30 flex items-center justify-center">
            <Eye size={14} className="text-accent" />
          </div>
          <div>
            <p className="font-display text-xs text-accent tracking-widest uppercase">
              SVS
            </p>
            <p className="text-ink-muted text-xs font-mono">v1.0 · Phase 4</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-4 space-y-0.5">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={clsx(active ? "nav-link-active" : "nav-link")}
            >
              <Icon size={16} />
              <span>{label}</span>
              {label === "Alerts" && highCount > 0 && (
                <span className="ml-auto bg-severity-high text-white text-xs font-mono px-1.5 py-0.5 rounded-full leading-none">
                  {highCount}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-2 py-3 border-t border-border space-y-1">
        <button
          onClick={logout}
          className="nav-link w-full text-left text-ink-muted hover:text-severity-high hover:bg-severity-high/10"
        >
          <LogOut size={16} />
          <span>Logout</span>
        </button>
        <p className="text-ink-muted text-xs font-mono px-2">
          © 2026 Smart Vision
        </p>
      </div>
    </aside>
  );
}
