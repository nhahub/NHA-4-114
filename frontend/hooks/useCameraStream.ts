import { useCallback } from "react";
import { useWebSocket } from "./useWebSocket";
import { useCameraStreamStore } from "@/lib/store";
import type { WSCameraFrame, ConnectionStatus } from "@/types";

export function useCameraStream(cameraId: number | null) {
  const setFrame = useCameraStreamStore((s) => s.setFrame);
  const setStatus = useCameraStreamStore((s) => s.setStatus);

  const onMessage = useCallback(
    (data: WSCameraFrame) => {
      setFrame(data);
    },
    [setFrame]
  );

  const onStatusChange = useCallback(
    (status: ConnectionStatus) => {
      setStatus(status);
    },
    [setStatus]
  );

  useWebSocket<WSCameraFrame>({
    path: `/ws/cameras/${cameraId}`,
    onMessage,
    onStatusChange,
    enabled: cameraId !== null,
  });
}
