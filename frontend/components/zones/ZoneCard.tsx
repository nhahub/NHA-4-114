"use client";

import { Zone } from "@/types";

interface Props {
  zone: Zone;
  onEdit: () => void;
  onDelete: () => void;
  deleting: boolean;
}

export default function ZoneCard({ zone, onEdit, onDelete, deleting }: Props) {
  const pointCount = zone.polygon.length;

  // Build a tiny SVG preview of the polygon (normalised to 80x50)
  const preview = buildPreview(zone.polygon);

  return (
    <div className="bg-surface-800 border border-surface-700 rounded-xl p-4 flex flex-col gap-4 hover:border-surface-500 transition">
      {/* Polygon mini-preview */}
      <div className="w-full h-24 bg-surface-900 rounded-lg flex items-center justify-center overflow-hidden">
        <svg viewBox="0 0 160 96" className="w-full h-full">
          {preview && (
            <polygon
              points={preview}
              fill="rgba(99,102,241,0.18)"
              stroke="#6366f1"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
          )}
        </svg>
      </div>

      {/* Info */}
      <div className="flex-1">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-white font-semibold text-sm truncate">{zone.name}</h3>
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${
              zone.is_active
                ? "bg-green-500/15 text-green-400"
                : "bg-surface-700 text-surface-400"
            }`}
          >
            {zone.is_active ? "Active" : "Inactive"}
          </span>
        </div>

        <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-surface-400">
          <div>
            <span className="text-surface-500">Threshold</span>
            <div className="text-white font-medium mt-0.5">{zone.threshold} persons</div>
          </div>
          <div>
            <span className="text-surface-500">Points</span>
            <div className="text-white font-medium mt-0.5">{pointCount} vertices</div>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2 pt-1 border-t border-surface-700">
        <button
          onClick={onEdit}
          className="flex-1 text-xs font-medium text-accent hover:text-white bg-accent/10 hover:bg-accent/20 rounded-lg py-1.5 transition"
        >
          Edit
        </button>
        <button
          onClick={onDelete}
          disabled={deleting}
          className="flex-1 text-xs font-medium text-severity-high hover:text-white bg-severity-high/10 hover:bg-severity-high/20 rounded-lg py-1.5 transition disabled:opacity-40"
        >
          {deleting ? "Deleting…" : "Delete"}
        </button>
      </div>
    </div>
  );
}

// Normalise polygon points to a 160×96 SVG viewBox
function buildPreview(polygon: number[][]): string | null {
  if (!polygon || polygon.length < 3) return null;

  const xs = polygon.map((p) => p[0]);
  const ys = polygon.map((p) => p[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const rangeX = maxX - minX || 1;
  const rangeY = maxY - minY || 1;

  const padding = 12;
  const W = 160 - padding * 2;
  const H = 96 - padding * 2;

  return polygon
    .map(([x, y]) => {
      const nx = padding + ((x - minX) / rangeX) * W;
      const ny = padding + ((y - minY) / rangeY) * H;
      return `${nx.toFixed(1)},${ny.toFixed(1)}`;
    })
    .join(" ");
}
