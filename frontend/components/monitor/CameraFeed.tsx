"use client";

import { useEffect, useRef } from "react";
import { useCameraStreamStore } from "@/lib/store";
import { useCameraStream } from "@/hooks/useCameraStream";
import TrackOverlay from "./TrackOverlay";
import clsx from "clsx";
import { WifiOff, Loader2 } from "lucide-react";

interface CameraFeedProps {
  cameraId: number;
  cameraName?: string;
}

export default function CameraFeed({ cameraId, cameraName }: CameraFeedProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  const frame = useCameraStreamStore((s) => s.frame);
  const status = useCameraStreamStore((s) => s.status);

  // Connect WebSocket for this camera
  useCameraStream(cameraId);

  // Render base64 frame onto canvas
  useEffect(() => {
    if (!frame || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const img = imgRef.current ?? new Image();
    imgRef.current = img;

    img.onload = () => {
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      ctx.drawImage(img, 0, 0);
    };
    img.src = `data:image/jpeg;base64,${frame.frame}`;
  }, [frame]);

  const isConnecting = status === "connecting";
  const isError = status === "disconnected" || status === "error";

  return (
    <div className="relative w-full aspect-video bg-surface-700 rounded-lg overflow-hidden border border-border">
      {/* Camera label */}
      <div className="absolute top-2 left-2 z-10 flex items-center gap-2">
        <span className="bg-surface-900/80 backdrop-blur-sm text-ink-primary text-xs font-mono px-2 py-1 rounded">
          {cameraName ?? `CAM-${cameraId}`}
        </span>
        {frame && (
          <span className="bg-surface-900/80 backdrop-blur-sm text-ink-secondary text-xs font-mono px-2 py-1 rounded">
            {frame.occupancy} ppl
          </span>
        )}
      </div>

      {/* Connection status badge */}
      <div className="absolute top-2 right-2 z-10">
        <span
          className={clsx(
            "flex items-center gap-1.5 text-xs font-mono px-2 py-1 rounded bg-surface-900/80 backdrop-blur-sm",
            {
              "text-severity-low": status === "connected",
              "text-severity-high": isError,
              "text-ink-muted": isConnecting,
            }
          )}
        >
          <span
            className={clsx("w-1.5 h-1.5 rounded-full", {
              "bg-severity-low animate-pulse-dot": status === "connected",
              "bg-severity-high": isError,
              "bg-ink-muted": isConnecting,
            })}
          />
          {status.toUpperCase()}
        </span>
      </div>

      {/* Canvas */}
      <canvas
        ref={canvasRef}
        className="w-full h-full object-contain"
        style={{ display: frame ? "block" : "none" }}
      />

      {/* Track overlay (SVG over canvas) */}
      {frame && (
        <TrackOverlay
          tracks={frame.tracks}
          canvasRef={canvasRef}
        />
      )}

      {/* Loading / offline state */}
      {!frame && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
          {isConnecting ? (
            <>
              <Loader2 size={24} className="text-ink-muted animate-spin" />
              <span className="text-ink-muted text-xs font-mono">
                Connecting to CAM-{cameraId}...
              </span>
            </>
          ) : isError ? (
            <>
              <WifiOff size={24} className="text-severity-high/50" />
              <span className="text-ink-muted text-xs font-mono">
                Stream unavailable
              </span>
            </>
          ) : (
            <span className="text-ink-muted text-xs font-mono">
              Waiting for stream...
            </span>
          )}
        </div>
      )}

      {/* Scanline effect */}
      <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(transparent_50%,rgba(0,0,0,0.03)_50%)] bg-[length:100%_4px]" />
    </div>
  );
}
