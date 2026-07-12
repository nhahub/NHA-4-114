import type { AlertSeverity } from "@/types";
import clsx from "clsx";

export default function AlertBadge({ severity }: { severity: AlertSeverity }) {
  return (
    <span
      className={clsx("px-2 py-0.5 rounded text-xs font-mono uppercase border", {
        "bg-severity-high-dim text-severity-high border-severity-high/30":
          severity === "high",
        "bg-severity-medium-dim text-severity-medium border-severity-medium/30":
          severity === "medium",
        "bg-severity-low-dim text-severity-low border-severity-low/30":
          severity === "low",
        "bg-severity-info-dim text-severity-info border-severity-info/30":
          severity === "info",
      })}
    >
      {severity}
    </span>
  );
}
