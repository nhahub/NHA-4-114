import { useEffect, useRef, useCallback } from "react";
import { wsUrl } from "@/lib/auth";
import type { ConnectionStatus } from "@/types";

const RECONNECT_DELAY_MS = 3_000;
const MAX_RECONNECT_ATTEMPTS = 10;

interface UseWebSocketOptions<T> {
  path: string;
  onMessage: (data: T) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
  enabled?: boolean;
}

export function useWebSocket<T>({
  path,
  onMessage,
  onStatusChange,
  enabled = true,
}: UseWebSocketOptions<T>) {
  const wsRef = useRef<WebSocket | null>(null);
  const attemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);

  const setStatus = useCallback(
    (status: ConnectionStatus) => onStatusChange?.(status),
    [onStatusChange]
  );

  const connect = useCallback(() => {
    if (!isMountedRef.current || !enabled) return;

    setStatus("connecting");

    const url = wsUrl(path);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMountedRef.current) return;
      attemptsRef.current = 0;
      setStatus("connected");
    };

    ws.onmessage = (event) => {
      if (!isMountedRef.current) return;
      try {
        const data: T = JSON.parse(event.data);
        onMessage(data);
      } catch {
        // ignore malformed frames
      }
    };

    ws.onerror = () => {
      setStatus("error");
    };

    ws.onclose = () => {
      if (!isMountedRef.current) return;
      setStatus("disconnected");

      if (attemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        attemptsRef.current += 1;
        reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
      }
    };
  }, [path, onMessage, setStatus, enabled]);

  useEffect(() => {
    isMountedRef.current = true;
    if (enabled) connect();

    return () => {
      isMountedRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, enabled]);
}
