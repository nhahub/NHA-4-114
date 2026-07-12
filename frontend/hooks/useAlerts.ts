import { useCallback } from "react";
import { useWebSocket } from "./useWebSocket";
import { isAuthenticated } from "@/lib/auth";
import { useAlertsStore } from "@/lib/store";
import type { WSAlert, ConnectionStatus } from "@/types";

export function useAlertsStream() {
  const pushAlert = useAlertsStore((s) => s.pushAlert);
  const setAlertStatus = useAlertsStore((s) => s.setAlertStatus);

  const onMessage = useCallback(
    (data: WSAlert) => {
      pushAlert(data);
    },
    [pushAlert]
  );

  const onStatusChange = useCallback(
    (status: ConnectionStatus) => {
      setAlertStatus(status);
    },
    [setAlertStatus]
  );

  useWebSocket<WSAlert>({
    path: "/ws/alerts",
    onMessage,
    onStatusChange,
    enabled: isAuthenticated(),
  });
}
