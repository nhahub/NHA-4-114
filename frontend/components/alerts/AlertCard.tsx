"use client";

import type { WSAlert, Alert } from "@/types";
import clsx from "clsx";
import { formatDistanceToNow } from "date-fns";
import { AlertTriangle, Info, Zap, MapPin } from "lucide-react";

type AlertItem = WSAlert | Alert;

interface AlertCardProps {
  alert: AlertItem;
  compact?: boolean;
}

const severityIcon = {
  high: AlertTriangle,
  medium: Zap,
  low: Info,
  info: Info,
};

const severityLabel = {
  high: "HIGH",
  medium: "MED",
  low: "LOW",
  info: "INFO",
};

const typeLabel: Record<string, string> = {
  zone_overcrowding: "Zone Overcrowding",
  loitering: "Loitering",
  crossing_event: "Crossing Event",
  zone_occupancy: "Zone Occupancy",
};

export default function AlertCard({ alert, compact = false }: AlertCardProps) {
  const Icon = severityIcon[alert.severity] ?? Info;
  const timeAgo = formatDistanceToNow(new Date(alert.timestamp), {
    addSuffix: true,
  });

  const md = (alert as WSAlert).metadata as Record<string, any> | undefined;

  return (
    <div
      className={clsx(
        "panel border-l-2 transition-all animate-fade-in",
        {
          "border-l-severity-high": alert.severity === "high",
          "border-l-severity-medium": alert.severity === "medium",
          "border-l-severity-low": alert.severity === "low",
          "border-l-severity-info": alert.severity === "info",
          "p-3": compact,
          "p-4": !compact,
        }
      )}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div
          className={clsx("mt-0.5 shrink-0", {
            "text-severity-high": alert.severity === "high",
            "text-severity-medium": alert.severity === "medium",
            "text-severity-low": alert.severity === "low",
            "text-severity-info": alert.severity === "info",
          })}
        >
          <Icon size={compact ? 14 : 16} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {/* Severity badge */}
            <span className={`badge-${alert.severity}`}>
              {severityLabel[alert.severity]}
            </span>
            {/* Type */}
            <span className="text-ink-secondary text-xs font-mono">
              {typeLabel[alert.type] ?? alert.type}
            </span>
            {/* Camera */}
            <span className="text-ink-muted text-xs font-mono ml-auto shrink-0">
              CAM-{alert.camera_id}
            </span>
          </div>

          {/* Message */}
          <p
            className={clsx("text-ink-primary font-sans mt-1", {
              "text-xs": compact,
              "text-sm": !compact,
            })}
          >
            {alert.message}
          </p>

          {/* Metadata (non-compact) */}
          {!compact && md && (
            <div className="flex items-center gap-3 mt-2 flex-wrap">
              {md.zone_name !== undefined && md.zone_name !== null && (
                <span className="flex items-center gap-1 text-xs font-mono text-ink-secondary">
                  <MapPin size={10} aria-hidden="true" />
                  <span className="sr-only">Zone:</span>
                  <span>{String(md.zone_name)}</span>
                </span>
              )}
              {md.duration_s !== undefined && md.duration_s !== null && (
                <span className="text-xs font-mono text-ink-secondary">
                  Duration: {String(md.duration_s)}s
                </span>
              )}
              {md.occupancy !== undefined && md.occupancy !== null && (
                <span className="text-xs font-mono text-ink-secondary">
                  Occupancy: {String(md.occupancy)}/{md.threshold !== undefined && md.threshold !== null ? String(md.threshold) : "—"}
                </span>
              )}
            </div>
          )}

          {/* Timestamp */}
          <p className="text-ink-muted text-xs font-mono mt-1.5">{timeAgo}</p>
        </div>
      </div>
    </div>
  );
}
