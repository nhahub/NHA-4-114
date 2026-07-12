"use client";

import { useEffect, useState, RefObject } from "react";
import type { Track } from "@/types";

interface TrackOverlayProps {
  tracks: Track[];
  canvasRef: RefObject<HTMLCanvasElement>;
}

interface ScaledTrack extends Track {
  sx1: number;
  sy1: number;
  sx2: number;
  sy2: number;
}

// Generate a consistent color per track_id
function trackColor(id: number): string {
  const hue = (id * 67) % 360;
  return `hsl(${hue}, 85%, 60%)`;
}

export default function TrackOverlay({ tracks, canvasRef }: TrackOverlayProps) {
  const [scaled, setScaled] = useState<ScaledTrack[]>([]);
  const [dims, setDims] = useState({ w: 0, h: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || tracks.length === 0) {
      setScaled([]);
      return;
    }

    const naturalW = canvas.width;
    const naturalH = canvas.height;
    const displayW = canvas.clientWidth;
    const displayH = canvas.clientHeight;

    if (!naturalW || !naturalH) return;

    const scaleX = displayW / naturalW;
    const scaleY = displayH / naturalH;

    setDims({ w: displayW, h: displayH });
    setScaled(
      tracks.map((t) => ({
        ...t,
        sx1: t.bbox[0] * scaleX,
        sy1: t.bbox[1] * scaleY,
        sx2: t.bbox[2] * scaleX,
        sy2: t.bbox[3] * scaleY,
      }))
    );
  }, [tracks, canvasRef]);

  if (scaled.length === 0) return null;

  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none"
      viewBox={`0 0 ${dims.w} ${dims.h}`}
      xmlns="http://www.w3.org/2000/svg"
    >
      {scaled.map((t) => {
        const color = trackColor(t.track_id);
        const w = t.sx2 - t.sx1;
        const h = t.sy2 - t.sy1;
        return (
          <g key={t.track_id}>
            {/* Bounding box */}
            <rect
              x={t.sx1}
              y={t.sy1}
              width={w}
              height={h}
              fill="none"
              stroke={color}
              strokeWidth={1.5}
              strokeOpacity={0.9}
            />
            {/* Corner accents */}
            <line x1={t.sx1} y1={t.sy1} x2={t.sx1 + 8} y2={t.sy1} stroke={color} strokeWidth={2} />
            <line x1={t.sx1} y1={t.sy1} x2={t.sx1} y2={t.sy1 + 8} stroke={color} strokeWidth={2} />
            <line x1={t.sx2} y1={t.sy1} x2={t.sx2 - 8} y2={t.sy1} stroke={color} strokeWidth={2} />
            <line x1={t.sx2} y1={t.sy1} x2={t.sx2} y2={t.sy1 + 8} stroke={color} strokeWidth={2} />
            {/* Track ID label */}
            <rect
              x={t.sx1}
              y={t.sy1 - 16}
              width={40}
              height={16}
              fill="rgba(8,12,18,0.75)"
              rx={2}
            />
            <text
              x={t.sx1 + 4}
              y={t.sy1 - 4}
              fill={color}
              fontSize={10}
              fontFamily="'JetBrains Mono', monospace"
              fontWeight={500}
            >
              #{t.track_id}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
