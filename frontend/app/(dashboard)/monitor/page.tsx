"use client";

import { useQuery } from "@tanstack/react-query";
import { camerasApi, analyticsApi } from "@/lib/api";
import { useCamerasStore, useCameraStreamStore } from "@/lib/store";
import { useEffect } from "react";
import CameraFeed from "@/components/monitor/CameraFeed";
import AlertCard from "@/components/alerts/AlertCard";
import { useAlertsStore } from "@/lib/store";
import { Users, ArrowUpRight, ArrowDownLeft, Bell } from "lucide-react";

export default function MonitorPage() {
  const setCameras = useCamerasStore((s) => s.setCameras);
  const cameras = useCamerasStore((s) => s.cameras);
  const activeCameraId = useCamerasStore((s) => s.activeCameraId);
  const setActiveCameraId = useCamerasStore((s) => s.setActiveCameraId);
  const frame = useCameraStreamStore((s) => s.frame);
  const liveAlerts = useAlertsStore((s) => s.liveAlerts);

  const { data: camerasData } = useQuery({
    queryKey: ["cameras"],
    queryFn: camerasApi.list,
    refetchInterval: 30_000,
  });

  const { data: summary } = useQuery({
    queryKey: ["analytics", "summary"],
    queryFn: analyticsApi.summary,
    refetchInterval: 10_000,
  });

  useEffect(() => {
    if (camerasData) setCameras(camerasData);
  }, [camerasData, setCameras]);

  const activeCamera = cameras.find((c) => c.id === activeCameraId);
  const recentAlerts = liveAlerts.slice(0, 5);

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Stat bar */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Current Occupancy"
          value={frame?.occupancy ?? summary?.current_occupancy ?? 0}
          icon={<Users size={14} className="text-accent" />}
          accent
        />
        <StatCard
          label="Total In"
          value={summary?.total_in ?? 0}
          icon={<ArrowUpRight size={14} className="text-severity-low" />}
        />
        <StatCard
          label="Total Out"
          value={summary?.total_out ?? 0}
          icon={<ArrowDownLeft size={14} className="text-severity-medium" />}
        />
        <StatCard
          label="Active Alerts"
          value={summary?.active_alerts ?? liveAlerts.length}
          icon={<Bell size={14} className="text-severity-high" />}
        />
      </div>

      <div className="flex gap-4 flex-1 min-h-0">
        {/* Main feed */}
        <div className="flex flex-col gap-3 flex-1 min-w-0">
          {/* Camera tabs */}
          {cameras.length > 0 && (
            <div className="flex gap-2 flex-wrap">
              {cameras.map((cam) => (
                <button
                  key={cam.id}
                  onClick={() => setActiveCameraId(cam.id)}
                  className={`text-xs font-mono px-3 py-1.5 rounded border transition-colors ${
                    cam.id === activeCameraId
                      ? "bg-accent/10 text-accent border-accent/40"
                      : "text-ink-secondary border-border hover:border-border-bright hover:text-ink-primary"
                  }`}
                >
                  {cam.name}
                  {!cam.is_active && (
                    <span className="ml-1 text-ink-muted">(off)</span>
                  )}
                </button>
              ))}
            </div>
          )}

          {/* Feed */}
          {activeCameraId ? (
            <CameraFeed
              cameraId={activeCameraId}
              cameraName={activeCamera?.name}
            />
          ) : (
            <div className="panel flex items-center justify-center aspect-video">
              <p className="text-ink-muted font-mono text-sm">
                No cameras configured
              </p>
            </div>
          )}

          {/* Zone occupancy */}
          {frame?.business_events && frame.business_events.filter((e) => e.type === "zone_occupancy").length > 0 && (
            <div className="panel px-4 py-2.5 flex items-center gap-4 flex-wrap">
              <span className="stat-label">Zones</span>
              <div className="flex gap-2 flex-wrap">
                {frame.business_events
                  .filter((e) => e.type === "zone_occupancy")
                  .map((e) => (
                    <span
                      key={e.zone_id}
                      className={`text-xs font-mono px-2 py-0.5 rounded border ${
                        e.occupancy >= e.threshold
                          ? "text-severity-high bg-severity-high/10 border-severity-high/30"
                          : "text-ink-secondary bg-surface-600 border-transparent"
                      }`}
                    >
                      {e.zone_name}: {e.occupancy}/{e.threshold}
                    </span>
                  ))}
              </div>
            </div>
          )}

          {/* Track count */}
          {frame && frame.tracks.length > 0 && (
            <div className="panel px-4 py-2.5 flex items-center gap-4 flex-wrap">
              <span className="stat-label">Tracked IDs</span>
              <div className="flex gap-2 flex-wrap">
                {frame.tracks.map((t) => (
                  <span
                    key={t.track_id}
                    className="text-xs font-mono text-ink-secondary bg-surface-600 px-2 py-0.5 rounded"
                  >
                    #{t.track_id}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar: live alerts */}
        <div className="w-72 shrink-0 hidden xl:flex flex-col gap-3">
          <div className="panel flex-1 flex flex-col min-h-0">
            <div className="panel-header">
              <span className="text-xs font-mono uppercase tracking-widest text-ink-secondary">
                Live Alerts
              </span>
              {liveAlerts.length > 0 && (
                <span className="text-xs font-mono text-ink-muted">
                  {liveAlerts.length} total
                </span>
              )}
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-2">
              {recentAlerts.length === 0 ? (
                <p className="text-ink-muted text-xs font-mono text-center py-8">
                  No alerts yet
                </p>
              ) : (
                recentAlerts.map((alert, i) => (
                  <AlertCard key={i} alert={alert} compact />
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
  accent = false,
}: {
  label: string;
  value: number;
  icon?: React.ReactNode;
  accent?: boolean;
}) {
  return (
    <div className={`panel p-4 ${accent ? "border-accent/20 shadow-accent" : ""}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="stat-label">{label}</span>
        {icon}
      </div>
      <p className={`text-2xl font-display ${accent ? "text-accent" : "text-ink-primary"}`}>
        {value}
      </p>
    </div>
  );
}
