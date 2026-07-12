"use client";

import { useQuery } from "@tanstack/react-query";
import { healthApi } from "@/lib/api";
import { useAlertsStore, useCameraStreamStore } from "@/lib/store";
import { useAlertsStream } from "@/hooks/useAlerts";
import { Activity, Wifi, WifiOff } from "lucide-react";
import clsx from "clsx";

export default function TopBar() {
  // Bootstrap the global alerts WebSocket for the entire app lifetime
  useAlertsStream();

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: healthApi.check,
    refetchInterval: 15_000,
  });

  const alertStatus = useAlertsStore((s) => s.alertStatus);
  const liveAlerts = useAlertsStore((s) => s.liveAlerts);
  const latestAlert = liveAlerts[0];

  const isHealthy =
    health?.status === "ok" &&
    health?.database === "connected" &&
    health?.redis === "connected";

  return (
    <header className="h-12 bg-surface-800 border-b border-border flex items-center justify-between px-4 shrink-0">
      {/* Left: latest alert ticker */}
      <div className="flex items-center gap-3 min-w-0">
        {latestAlert ? (
          <>
            <span
              className={clsx("w-1.5 h-1.5 rounded-full shrink-0 animate-pulse-dot", {
                "bg-severity-high": latestAlert.severity === "high",
                "bg-severity-medium": latestAlert.severity === "medium",
                "bg-severity-low": latestAlert.severity === "low",
              })}
            />
            <span className="text-xs font-mono text-ink-secondary truncate">
              <span className="text-ink-primary">LATEST · </span>
              {latestAlert.message}
            </span>
          </>
        ) : (
          <span className="text-xs font-mono text-ink-muted">
            No active alerts
          </span>
        )}
      </div>

      {/* Right: status indicators */}
      <div className="flex items-center gap-4 shrink-0">
        {/* WS Status */}
        <div className="flex items-center gap-1.5">
          {alertStatus === "connected" ? (
            <Wifi size={13} className="text-severity-low" />
          ) : (
            <WifiOff size={13} className="text-ink-muted" />
          )}
          <span className="text-xs font-mono text-ink-secondary hidden sm:block">
            WS
          </span>
        </div>

        {/* System Health */}
        <div className="flex items-center gap-1.5">
          <Activity
            size={13}
            className={isHealthy ? "text-severity-low" : "text-severity-high"}
          />
          <span
            className={clsx("text-xs font-mono hidden sm:block", {
              "text-severity-low": isHealthy,
              "text-severity-high": !isHealthy,
              "text-ink-muted": health === undefined,
            })}
          >
            {health ? (isHealthy ? "ONLINE" : "DEGRADED") : "CHECKING"}
          </span>
        </div>

        {/* DB */}
        <div className="hidden md:flex items-center gap-1.5">
          <span
            className={clsx("w-1.5 h-1.5 rounded-full", {
              "bg-severity-low": health?.database === "connected",
              "bg-severity-high": health?.database === "disconnected",
              "bg-ink-muted": health === undefined,
            })}
          />
          <span className="text-xs font-mono text-ink-secondary">DB</span>
        </div>

        {/* Redis */}
        <div className="hidden md:flex items-center gap-1.5">
          <span
            className={clsx("w-1.5 h-1.5 rounded-full", {
              "bg-severity-low": health?.redis === "connected",
              "bg-severity-high": health?.redis === "disconnected",
              "bg-ink-muted": health === undefined,
            })}
          />
          <span className="text-xs font-mono text-ink-secondary">Redis</span>
        </div>
      </div>
    </header>
  );
}
