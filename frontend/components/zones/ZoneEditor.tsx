"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import { Camera, Zone } from "@/types";
import { useCameraStream } from "@/hooks/useCameraStream";
import { useCameraStreamStore } from "@/lib/store";

interface Props {
  camera: Camera;
  existingZone: Zone | null;
  onSaved: () => void;
  onClose: () => void;
}

export default function ZoneEditor({ camera, existingZone, onSaved, onClose }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<SVGSVGElement>(null);

  const streamFrame = useCameraStreamStore((s) => s.frame);
  useCameraStream(camera.id);
  const frameData = streamFrame?.frame;
  const occupancy = streamFrame?.occupancy;

  // Polygon points in canvas pixel space
  const [points, setPoints] = useState<[number, number][]>(
    existingZone ? (existingZone.polygon as [number, number][]) : []
  );
  const [closed, setClosed] = useState(existingZone !== null);
  const [hovering, setHovering] = useState(false);

  // Form fields
  const [name, setName] = useState(existingZone?.name ?? "");
  const [threshold, setThreshold] = useState(existingZone?.threshold ?? 5);
  const [isActive, setIsActive] = useState(existingZone?.is_active ?? true);
  const [error, setError] = useState<string | null>(null);

  // ── Draw camera frame onto canvas ────────────────────────────────────────
  useEffect(() => {
    if (!frameData || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const img = new Image();
    img.onload = () => {
      canvas.width = img.naturalWidth || 640;
      canvas.height = img.naturalHeight || 360;
      ctx.drawImage(img, 0, 0);
    };
    img.src = `data:image/jpeg;base64,${frameData}`;
  }, [frameData]);

  // ── Canvas click → add point ─────────────────────────────────────────────
  const handleCanvasClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (closed) return;

      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      const x = Math.round((e.clientX - rect.left) * scaleX);
      const y = Math.round((e.clientY - rect.top) * scaleY);

      // Close polygon if clicking near the first point (within 12px)
      if (points.length >= 3) {
        const [fx, fy] = points[0];
        const dx = (fx / scaleX) - (e.clientX - rect.left);
        const dy = (fy / scaleY) - (e.clientY - rect.top);
        if (Math.hypot(dx, dy) < 12) {
          setClosed(true);
          return;
        }
      }

      setPoints((prev) => [...prev, [x, y]]);
    },
    [closed, points]
  );

  // Right-click → close polygon
  const handleRightClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      e.preventDefault();
      if (points.length >= 3) setClosed(true);
    },
    [points]
  );

  function resetPolygon() {
    setPoints([]);
    setClosed(false);
  }

  function undoLastPoint() {
    if (closed) {
      setClosed(false);
    } else {
      setPoints((prev) => prev.slice(0, -1));
    }
  }

  // ── SVG overlay points (scaled to display size) ──────────────────────────
  function canvasToDisplay(x: number, y: number): [number, number] {
    const canvas = canvasRef.current;
    if (!canvas) return [x, y];
    const rect = canvas.getBoundingClientRect();
    const scaleX = rect.width / (canvas.width || 640);
    const scaleY = rect.height / (canvas.height || 360);
    return [x * scaleX, y * scaleY];
  }

  // ── Save mutation ─────────────────────────────────────────────────────────
  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!name.trim()) throw new Error("Zone name is required");
      if (points.length < 3) throw new Error("Draw at least 3 points");

      const payload = {
        camera_id: camera.id,
        name: name.trim(),
        polygon: points,
        threshold,
        is_active: isActive,
      };

      if (existingZone) {
        return apiClient.updateZone(existingZone.id, payload);
      } else {
        return apiClient.createZone(payload);
      }
    },
    onSuccess: onSaved,
    onError: (err: Error) => setError(err.message),
  });

  // ── Build SVG polyline/polygon string ────────────────────────────────────
  const svgPoints = points.map(([x, y]) => {
    const [dx, dy] = canvasToDisplay(x, y);
    return `${dx},${dy}`;
  });

  return (
    // Modal backdrop
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-4xl bg-surface-800 border border-surface-700 rounded-2xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-700 shrink-0">
          <div>
            <h2 className="text-white font-bold text-base">
              {existingZone ? "Edit Zone" : "New Zone"} — {camera.name}
            </h2>
            <p className="text-xs text-surface-400 mt-0.5">
              Click canvas to add points · Right-click or click first point to close · Undo with ↩
            </p>
          </div>
          <button onClick={onClose} className="text-surface-400 hover:text-white transition p-1">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex flex-1 overflow-hidden divide-x divide-surface-700">

          {/* Left: canvas + drawing */}
          <div className="flex-1 flex flex-col p-4 gap-3 min-w-0">
            {/* Toolbar */}
            <div className="flex gap-2 shrink-0">
              <button
                onClick={undoLastPoint}
                disabled={points.length === 0}
                className="text-xs px-3 py-1.5 rounded-lg bg-surface-700 hover:bg-surface-600 text-white disabled:opacity-40 transition"
              >
                ↩ Undo
              </button>
              <button
                onClick={resetPolygon}
                disabled={points.length === 0}
                className="text-xs px-3 py-1.5 rounded-lg bg-surface-700 hover:bg-surface-600 text-white disabled:opacity-40 transition"
              >
                ✕ Reset
              </button>
              {points.length >= 3 && !closed && (
                <button
                  onClick={() => setClosed(true)}
                  className="text-xs px-3 py-1.5 rounded-lg bg-accent/20 hover:bg-accent/30 text-accent transition"
                >
                  ⬡ Close polygon
                </button>
              )}
              {closed && (
                <span className="text-xs px-3 py-1.5 rounded-lg bg-green-500/15 text-green-400 font-medium">
                  ✓ Polygon closed ({points.length} points)
                </span>
              )}
            </div>

            {/* Canvas area */}
            <div
              className="relative flex-1 rounded-xl overflow-hidden bg-black cursor-crosshair"
              style={{ minHeight: 240 }}
            >
              <canvas
                ref={canvasRef}
                className="w-full h-full object-contain"
                onClick={handleCanvasClick}
                onContextMenu={handleRightClick}
                onMouseEnter={() => setHovering(true)}
                onMouseLeave={() => setHovering(false)}
              />

              {/* No frame yet */}
              {!frameData && (
                <div className="absolute inset-0 flex items-center justify-center text-surface-500 text-sm">
                  Connecting to camera stream…
                </div>
              )}

              {/* SVG overlay for polygon drawing */}
              <svg
                ref={overlayRef}
                className="absolute inset-0 w-full h-full pointer-events-none"
                viewBox={`0 0 ${canvasRef.current?.getBoundingClientRect().width ?? 640} ${canvasRef.current?.getBoundingClientRect().height ?? 360}`}
                preserveAspectRatio="none"
              >
                {/* Filled polygon if closed */}
                {closed && points.length >= 3 && (
                  <polygon
                    points={svgPoints.join(" ")}
                    fill="rgba(99,102,241,0.22)"
                    stroke="#6366f1"
                    strokeWidth="2"
                    strokeLinejoin="round"
                  />
                )}

                {/* Open polyline */}
                {!closed && points.length >= 2 && (
                  <polyline
                    points={svgPoints.join(" ")}
                    fill="none"
                    stroke="#6366f1"
                    strokeWidth="2"
                    strokeDasharray="6 3"
                    strokeLinejoin="round"
                  />
                )}

                {/* Vertex dots */}
                {points.map(([x, y], i) => {
                  const [dx, dy] = canvasToDisplay(x, y);
                  const isFirst = i === 0;
                  return (
                    <g key={i}>
                      <circle
                        cx={dx}
                        cy={dy}
                        r={isFirst && !closed ? 7 : 4}
                        fill={isFirst && !closed ? "rgba(99,102,241,0.4)" : "#6366f1"}
                        stroke="white"
                        strokeWidth="1.5"
                      />
                      {isFirst && !closed && points.length >= 3 && (
                        <circle cx={dx} cy={dy} r={11} fill="none" stroke="#6366f1" strokeWidth="1" strokeDasharray="3 2" />
                      )}
                    </g>
                  );
                })}
              </svg>

              {/* Occupancy badge */}
              {occupancy !== undefined && (
                <div className="absolute top-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded-md">
                  Occupancy: {occupancy}
                </div>
              )}
            </div>
          </div>

          {/* Right: zone configuration */}
          <div className="w-72 shrink-0 flex flex-col p-5 gap-5 overflow-y-auto">
            <div>
              <h3 className="text-xs font-semibold text-surface-400 uppercase tracking-wider mb-3">
                Zone Settings
              </h3>

              <div className="space-y-4">
                {/* Name */}
                <div>
                  <label className="block text-xs text-surface-300 mb-1.5">Zone Name</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Entrance, Checkout"
                    className="w-full bg-surface-900 border border-surface-600 rounded-lg px-3 py-2 text-sm text-white placeholder-surface-500 focus:outline-none focus:ring-2 focus:ring-accent"
                  />
                </div>

                {/* Threshold */}
                <div>
                  <label className="block text-xs text-surface-300 mb-1.5">
                    Capacity Threshold
                    <span className="ml-1.5 text-surface-500">(alert fires above this)</span>
                  </label>
                  <div className="flex items-center gap-3">
                    <input
                      type="range"
                      min={1}
                      max={50}
                      value={threshold}
                      onChange={(e) => setThreshold(Number(e.target.value))}
                      className="flex-1 accent-indigo-500"
                    />
                    <span className="text-white font-bold text-sm w-8 text-right">{threshold}</span>
                  </div>
                </div>

                {/* Active toggle */}
                <div className="flex items-center justify-between">
                  <label className="text-xs text-surface-300">Zone Active</label>
                  <button
                    onClick={() => setIsActive((v) => !v)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
                      isActive ? "bg-accent" : "bg-surface-600"
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition ${
                        isActive ? "translate-x-6" : "translate-x-1"
                      }`}
                    />
                  </button>
                </div>
              </div>
            </div>

            {/* Polygon status */}
            <div className="bg-surface-900 rounded-lg p-3 text-xs space-y-1">
              <div className="flex justify-between text-surface-400">
                <span>Points drawn</span>
                <span className="text-white">{points.length}</span>
              </div>
              <div className="flex justify-between text-surface-400">
                <span>Status</span>
                <span className={closed ? "text-green-400" : "text-yellow-400"}>
                  {points.length === 0
                    ? "Not started"
                    : closed
                    ? "Closed ✓"
                    : "Drawing…"}
                </span>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="text-xs text-severity-high bg-severity-high/10 border border-severity-high/30 rounded-lg p-3">
                {error}
              </div>
            )}

            {/* Save / Cancel */}
            <div className="mt-auto flex flex-col gap-2">
              <button
                onClick={() => saveMutation.mutate()}
                disabled={!closed || !name.trim() || saveMutation.isPending}
                className="w-full bg-accent hover:bg-accent/80 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-semibold py-2.5 rounded-lg transition"
              >
                {saveMutation.isPending
                  ? "Saving…"
                  : existingZone
                  ? "Update Zone"
                  : "Save Zone"}
              </button>
              <button
                onClick={onClose}
                className="w-full bg-surface-700 hover:bg-surface-600 text-white text-sm font-medium py-2.5 rounded-lg transition"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
