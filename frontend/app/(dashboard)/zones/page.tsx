"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import { Camera, Zone } from "@/types";
import ZoneCard from "@/components/zones/ZoneCard";
import ZoneEditor from "@/components/zones/ZoneEditor";

export default function ZonesPage() {
  const queryClient = useQueryClient();
  const [selectedCameraId, setSelectedCameraId] = useState<number | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingZone, setEditingZone] = useState<Zone | null>(null);

  // ── Cameras list ─────────────────────────────────────────────────────────
  const { data: cameras = [] } = useQuery<Camera[]>({
    queryKey: ["cameras"],
    queryFn: () => apiClient.getCameras(),
  });

  // ── Zones list for selected camera ───────────────────────────────────────
  const { data: zones = [], isLoading: zonesLoading } = useQuery<Zone[]>({
    queryKey: ["zones", selectedCameraId],
    queryFn: () => apiClient.getZones(selectedCameraId!),
    enabled: selectedCameraId !== null,
  });

  // ── Delete mutation ───────────────────────────────────────────────────────
  const deleteMutation = useMutation({
    mutationFn: (zoneId: number) => apiClient.deleteZone(zoneId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["zones", selectedCameraId] }),
  });

  function openCreateEditor() {
    setEditingZone(null);
    setEditorOpen(true);
  }

  function openEditEditor(zone: Zone) {
    setEditingZone(zone);
    setEditorOpen(true);
  }

  function onEditorSaved() {
    setEditorOpen(false);
    setEditingZone(null);
    queryClient.invalidateQueries({ queryKey: ["zones", selectedCameraId] });
  }

  const selectedCamera = cameras.find((c) => c.id === selectedCameraId) ?? null;

  return (
    <div className="flex flex-col h-full gap-6 p-6">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Zone Management</h1>
          <p className="text-sm text-surface-400 mt-0.5">
            Draw polygon zones on camera feeds to monitor occupancy and trigger alerts.
          </p>
        </div>
        {selectedCameraId && (
          <button
            onClick={openCreateEditor}
            className="flex items-center gap-2 bg-accent hover:bg-accent/80 text-white text-sm font-semibold px-4 py-2 rounded-lg transition"
          >
            <span className="text-lg leading-none">+</span> New Zone
          </button>
        )}
      </div>

      {/* ── Camera selector ── */}
      <div className="bg-surface-800 border border-surface-700 rounded-xl p-4">
        <label className="block text-xs font-medium text-surface-400 uppercase tracking-wider mb-2">
          Select Camera
        </label>
        <select
          value={selectedCameraId ?? ""}
          onChange={(e) =>
            setSelectedCameraId(e.target.value ? Number(e.target.value) : null)
          }
          className="w-full max-w-xs bg-surface-900 border border-surface-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-accent"
        >
          <option value="">— Choose a camera —</option>
          {cameras.map((cam) => (
            <option key={cam.id} value={cam.id}>
              {cam.name} {cam.is_active ? "" : "(inactive)"}
            </option>
          ))}
        </select>
      </div>

      {/* ── Zone list ── */}
      {selectedCameraId === null ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-surface-500">
            <svg className="w-16 h-16 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.2}
                d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-1.447-.894L15 9m0 8V9m0 0L9 7" />
            </svg>
            <p className="text-sm">Select a camera to view and manage its zones</p>
          </div>
        </div>
      ) : zonesLoading ? (
        <div className="flex-1 flex items-center justify-center text-surface-400 text-sm">
          Loading zones…
        </div>
      ) : zones.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-4">
          <div className="text-center text-surface-500">
            <svg className="w-14 h-14 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.2}
                d="M12 4v16m8-8H4" />
            </svg>
            <p className="text-sm">No zones defined for this camera yet.</p>
          </div>
          <button
            onClick={openCreateEditor}
            className="bg-accent hover:bg-accent/80 text-white text-sm font-semibold px-5 py-2.5 rounded-lg transition"
          >
            Draw First Zone
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {zones.map((zone) => (
            <ZoneCard
              key={zone.id}
              zone={zone}
              onEdit={() => openEditEditor(zone)}
              onDelete={() => deleteMutation.mutate(zone.id)}
              deleting={deleteMutation.isPending}
            />
          ))}
        </div>
      )}

      {/* ── Zone Editor modal ── */}
      {editorOpen && selectedCamera && (
        <ZoneEditor
          camera={selectedCamera}
          existingZone={editingZone}
          onSaved={onEditorSaved}
          onClose={() => {
            setEditorOpen(false);
            setEditingZone(null);
          }}
        />
      )}
    </div>
  );
}
