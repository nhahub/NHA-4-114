"use client";

import { useQuery } from "@tanstack/react-query";
import { analyticsApi, camerasApi } from "@/lib/api";
import { useCamerasStore, useCameraStreamStore } from "@/lib/store";
import { useCameraStream } from "@/hooks/useCameraStream";
import OccupancyChart from "@/components/analytics/OccupancyChart";
import { useEffect, useRef, useState } from "react";
import type { WSCameraFrame } from "@/types";
import { Users, TrendingUp, TrendingDown, Activity } from "lucide-react";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function AnalyticsPage() {
  const setCameras = useCamerasStore((s) => s.setCameras);
  const activeCameraId = useCamerasStore((s) => s.activeCameraId);
  const frame = useCameraStreamStore((s) => s.frame);

  // Analytics has its own live feed — it must not depend on the Monitor page
  // being mounted (that page owns a separate instance of this same hook, and
  // the socket closes on unmount, which is why the chart used to never get
  // data when navigating here directly).
  const { data: camerasData } = useQuery({
    queryKey: ["cameras"],
    queryFn: camerasApi.list,
    refetchInterval: 30_000,
  });

  useEffect(() => {
    if (camerasData) setCameras(camerasData);
  }, [camerasData, setCameras]);

  useCameraStream(activeCameraId);

  // Accumulate occupancy samples for the chart
  const [chartData, setChartData] = useState<
    { timestamp: string; occupancy: number }[]
  >([]);
  const lastSampleRef = useRef<number>(0);

  useEffect(() => {
    if (!frame) return;
    const now = Date.now();
    // Sample once every 5 seconds
    if (now - lastSampleRef.current < 5_000) return;
    lastSampleRef.current = now;
    setChartData((prev) =>
      [...prev, { timestamp: frame.timestamp, occupancy: frame.occupancy }].slice(-60)
    );
  }, [frame]);

  const { data: summary } = useQuery({
    queryKey: ["analytics", "summary"],
    queryFn: analyticsApi.summary,
    refetchInterval: 10_000,
  });

  const { data: zones } = useQuery({
    queryKey: ["analytics", "zones", activeCameraId],
    queryFn: () => analyticsApi.zones(activeCameraId!),
    enabled: !!activeCameraId,
    refetchInterval: 10_000,
  });

  const { data: heatmap } = useQuery({
    queryKey: ["analytics", "heatmap", activeCameraId],
    queryFn: () => analyticsApi.heatmap(activeCameraId!),
    enabled: !!activeCameraId,
    refetchInterval: 30_000,
  });

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div>
        <h1 className="font-display text-lg text-ink-primary">Analytics</h1>
        <p className="text-ink-secondary text-xs font-mono mt-0.5">
          Occupancy, zone intelligence, and density heatmaps
        </p>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          {
            label: "Current Occupancy",
            value: frame?.occupancy ?? summary?.current_occupancy ?? 0,
            icon: <Users size={14} className="text-accent" />,
            accent: true,
          },
          {
            label: "Total In",
            value: summary?.total_in ?? 0,
            icon: <TrendingUp size={14} className="text-severity-low" />,
          },
          {
            label: "Total Out",
            value: summary?.total_out ?? 0,
            icon: <TrendingDown size={14} className="text-severity-medium" />,
          },
          {
            label: "Active Alerts",
            value: summary?.active_alerts ?? 0,
            icon: <Activity size={14} className="text-severity-high" />,
          },
        ].map(({ label, value, icon, accent }) => (
          <div
            key={label}
            className={`panel p-4 ${accent ? "border-accent/20 shadow-accent" : ""}`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="stat-label">{label}</span>
              {icon}
            </div>
            <p
              className={`text-2xl font-display ${
                accent ? "text-accent" : "text-ink-primary"
              }`}
            >
              {value}
            </p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Occupancy chart */}
        <div className="panel lg:col-span-2">
          <div className="panel-header">
            <span className="text-xs font-mono uppercase tracking-widest text-ink-secondary">
              Live Occupancy
            </span>
            <span className="text-xs font-mono text-ink-muted">
              Last {chartData.length} samples
            </span>
          </div>
          <div className="p-4">
            {chartData.length < 2 ? (
              <div className="h-48 flex items-center justify-center">
                <p className="text-ink-muted text-xs font-mono">
                  Collecting data from live stream...
                </p>
              </div>
            ) : (
              <OccupancyChart data={chartData} height={192} />
            )}
          </div>
        </div>

        {/* Zone stats */}
        <div className="panel">
          <div className="panel-header">
            <span className="text-xs font-mono uppercase tracking-widest text-ink-secondary">
              Zone Status
            </span>
          </div>
          <div className="p-3 space-y-3">
            {!zones || zones.zones.length === 0 ? (
              <p className="text-ink-muted text-xs font-mono text-center py-6">
                No zones configured
              </p>
            ) : (
              zones.zones.map((zone) => {
                const pct = Math.min(
                  100,
                  Math.round((zone.occupancy / zone.threshold) * 100)
                );
                const isOver = zone.occupancy >= zone.threshold;
                return (
                  <div key={zone.zone_id}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-mono text-ink-primary">
                        {zone.name}
                      </span>
                      <span
                        className={`text-xs font-mono ${
                          isOver ? "text-severity-high" : "text-severity-low"
                        }`}
                      >
                        {zone.occupancy}/{zone.threshold}
                      </span>
                    </div>
                    <div className="h-1.5 bg-surface-600 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          isOver ? "bg-severity-high" : "bg-severity-low"
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Heatmap */}
      {activeCameraId && (
        <div className="panel">
          <div className="panel-header">
            <span className="text-xs font-mono uppercase tracking-widest text-ink-secondary">
              Density Heatmap — CAM-{activeCameraId}
            </span>
          </div>
          <div className="p-4">
            {heatmap?.heatmap_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={`${BASE_URL}${heatmap.heatmap_url}`}
                alt="Density heatmap"
                className="w-full rounded border border-border object-contain max-h-96"
              />
            ) : (
              <div className="h-48 flex items-center justify-center">
                <p className="text-ink-muted text-xs font-mono">
                  No heatmap generated yet
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
