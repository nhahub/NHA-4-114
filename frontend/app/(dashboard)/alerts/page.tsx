"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { alertsApi } from "@/lib/api";
import { useAlertsStore } from "@/lib/store";
import AlertCard from "@/components/alerts/AlertCard";
import type { AlertSeverity } from "@/types";
import { RefreshCw } from "lucide-react";

const SEVERITY_FILTERS: { label: string; value: AlertSeverity | "all" }[] = [
  { label: "All", value: "all" },
  { label: "High", value: "high" },
  { label: "Medium", value: "medium" },
  { label: "Low", value: "low" },
];

export default function AlertsPage() {
  const [severity, setSeverity] = useState<AlertSeverity | "all">("all");
  const [page, setPage] = useState(1);
  const [tab, setTab] = useState<"live" | "history">("live");

  const liveAlerts = useAlertsStore((s) => s.liveAlerts);
  const clearAlerts = useAlertsStore((s) => s.clearAlerts);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["alerts", severity, page],
    queryFn: () =>
      alertsApi.list({
        page,
        limit: 20,
        ...(severity !== "all" && { severity }),
      }),
    enabled: tab === "history",
  });

  const filteredLive =
    severity === "all"
      ? liveAlerts
      : liveAlerts.filter((a) => a.severity === severity);

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-lg text-ink-primary">Alerts</h1>
          <p className="text-ink-secondary text-xs font-mono mt-0.5">
            Real-time and historical alert feed
          </p>
        </div>
        {tab === "live" && liveAlerts.length > 0 && (
          <button
            onClick={clearAlerts}
            className="btn-ghost text-xs"
          >
            Clear live
          </button>
        )}
        {tab === "history" && (
          <button
            onClick={() => refetch()}
            className="btn-ghost flex items-center gap-2 text-xs"
          >
            <RefreshCw size={12} />
            Refresh
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-border pb-0">
        {(["live", "history"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-mono capitalize border-b-2 -mb-px transition-colors ${
              tab === t
                ? "border-accent text-accent"
                : "border-transparent text-ink-secondary hover:text-ink-primary"
            }`}
          >
            {t === "live" ? `Live (${liveAlerts.length})` : "History"}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-mono text-ink-muted uppercase tracking-widest">
          Severity:
        </span>
        {SEVERITY_FILTERS.map(({ label, value }) => (
          <button
            key={value}
            onClick={() => { setSeverity(value); setPage(1); }}
            className={`px-3 py-1 text-xs font-mono rounded border transition-colors ${
              severity === value
                ? "bg-accent/10 text-accent border-accent/40"
                : "text-ink-secondary border-border hover:border-border-bright hover:text-ink-primary"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Content */}
      {tab === "live" ? (
        <div className="space-y-2">
          {filteredLive.length === 0 ? (
            <EmptyState message="No live alerts" />
          ) : (
            filteredLive.map((alert, i) => (
              <AlertCard key={i} alert={alert} />
            ))
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {isLoading ? (
            <Loading />
          ) : (data?.items ?? []).length === 0 ? (
            <EmptyState message="No alerts found" />
          ) : (
            <>
              {data!.items.map((alert) => (
                <AlertCard key={alert.id} alert={alert} />
              ))}
              {/* Pagination */}
              <div className="flex items-center justify-between pt-2">
                <span className="text-xs font-mono text-ink-muted">
                  Page {data!.page} · {data!.total} total
                </span>
                <div className="flex gap-2">
                  <button
                    disabled={page === 1}
                    onClick={() => setPage((p) => p - 1)}
                    className="btn-ghost text-xs disabled:opacity-40"
                  >
                    Prev
                  </button>
                  <button
                    disabled={page * data!.limit >= data!.total}
                    onClick={() => setPage((p) => p + 1)}
                    className="btn-ghost text-xs disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="panel py-16 flex items-center justify-center">
      <p className="text-ink-muted font-mono text-sm">{message}</p>
    </div>
  );
}

function Loading() {
  return (
    <div className="panel py-16 flex items-center justify-center">
      <p className="text-ink-muted font-mono text-sm animate-pulse">Loading...</p>
    </div>
  );
}
