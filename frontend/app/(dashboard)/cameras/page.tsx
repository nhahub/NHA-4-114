"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { camerasApi } from "@/lib/api";
import { useCamerasStore } from "@/lib/store";
import type { Camera, CameraCreate, SourceType } from "@/types";
import { Plus, Pencil, Trash2, CheckCircle, XCircle } from "lucide-react";

const defaultForm: CameraCreate = {
  name: "",
  source_type: "rtsp",
  source_url: "",
  is_active: true,
};

export default function CamerasPage() {
  const queryClient = useQueryClient();
  const setCameras = useCamerasStore((s) => s.setCameras);

  const [showForm, setShowForm] = useState(false);
  const [editCamera, setEditCamera] = useState<Camera | null>(null);
  const [form, setForm] = useState<CameraCreate>(defaultForm);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const { data: cameras = [], isLoading } = useQuery({
    queryKey: ["cameras"],
    queryFn: camerasApi.list,
  });

  useEffect(() => {
    if (cameras) setCameras(cameras);
  }, [cameras, setCameras]);

  const createMutation = useMutation({
    mutationFn: camerasApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cameras"] });
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<CameraCreate> }) =>
      camerasApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cameras"] });
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: camerasApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cameras"] });
      setDeleteId(null);
    },
  });

  function resetForm() {
    setForm(defaultForm);
    setShowForm(false);
    setEditCamera(null);
  }

  function openEdit(camera: Camera) {
    setEditCamera(camera);
    setForm({
      name: camera.name,
      source_type: camera.source_type,
      source_url: camera.source_url,
      is_active: camera.is_active,
    });
    setShowForm(true);
  }

  function handleSubmit() {
    if (!form.name || !form.source_url) return;
    if (editCamera) {
      updateMutation.mutate({ id: editCamera.id, data: form });
    } else {
      createMutation.mutate(form);
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-lg text-ink-primary">Cameras</h1>
          <p className="text-ink-secondary text-xs font-mono mt-0.5">
            Manage camera sources and configuration
          </p>
        </div>
        <button
          onClick={() => { resetForm(); setShowForm(true); }}
          className="btn-primary flex items-center gap-2"
        >
          <Plus size={14} />
          Add Camera
        </button>
      </div>

      {/* Form */}
      {showForm && (
        <div className="panel p-4 border-accent/20 shadow-accent animate-fade-in">
          <h2 className="text-sm font-mono text-ink-primary mb-4">
            {editCamera ? `Edit — ${editCamera.name}` : "New Camera"}
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono text-ink-secondary uppercase tracking-widest">
                Name
              </label>
              <input
                className="input-field"
                placeholder="Front Entrance"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono text-ink-secondary uppercase tracking-widest">
                Source Type
              </label>
              <select
                className="input-field"
                value={form.source_type}
                onChange={(e) =>
                  setForm({ ...form, source_type: e.target.value as SourceType })
                }
              >
                <option value="rtsp">RTSP</option>
                <option value="usb">USB</option>
                <option value="file">File</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <label className="text-xs font-mono text-ink-secondary uppercase tracking-widest">
                Source URL / Path
              </label>
              <input
                className="input-field"
                placeholder="rtsp://192.168.1.100:554/stream"
                value={form.source_url}
                onChange={(e) => setForm({ ...form, source_url: e.target.value })}
              />
            </div>
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="is_active"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                className="accent-accent"
              />
              <label
                htmlFor="is_active"
                className="text-sm font-mono text-ink-secondary cursor-pointer"
              >
                Active
              </label>
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button
              onClick={handleSubmit}
              disabled={isPending || !form.name || !form.source_url}
              className="btn-primary"
            >
              {isPending
                ? "Saving..."
                : editCamera
                ? "Save Changes"
                : "Create Camera"}
            </button>
            <button onClick={resetForm} className="btn-ghost">
              Cancel
            </button>
          </div>
          {(createMutation.isError || updateMutation.isError) && (
            <p className="text-severity-high text-xs font-mono mt-2">
              Failed to save camera. Check your backend connection.
            </p>
          )}
        </div>
      )}

      {/* Camera list */}
      {isLoading ? (
        <div className="panel py-16 flex items-center justify-center">
          <p className="text-ink-muted font-mono text-sm animate-pulse">
            Loading cameras...
          </p>
        </div>
      ) : cameras.length === 0 ? (
        <div className="panel py-16 flex flex-col items-center justify-center gap-3">
          <p className="text-ink-muted font-mono text-sm">
            No cameras configured
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="btn-primary text-xs"
          >
            Add your first camera
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {cameras.map((cam) => (
            <div
              key={cam.id}
              className="panel p-4 flex items-center gap-4 hover:border-border-bright transition-colors"
            >
              {/* Status dot */}
              <div
                className={`w-2 h-2 rounded-full shrink-0 ${
                  cam.is_active
                    ? "bg-severity-low animate-pulse-dot"
                    : "bg-ink-muted"
                }`}
              />

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-ink-primary font-mono text-sm font-medium">
                    {cam.name}
                  </p>
                  <span className="text-xs font-mono text-ink-muted bg-surface-600 px-1.5 py-0.5 rounded uppercase">
                    {cam.source_type}
                  </span>
                  {cam.is_active ? (
                    <span className="flex items-center gap-1 text-xs font-mono text-severity-low">
                      <CheckCircle size={11} /> Active
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs font-mono text-ink-muted">
                      <XCircle size={11} /> Inactive
                    </span>
                  )}
                </div>
                <p className="text-ink-muted text-xs font-mono mt-0.5 truncate">
                  {cam.source_url}
                </p>
              </div>

              {/* ID */}
              <span className="text-ink-muted text-xs font-mono hidden sm:block">
                ID:{cam.id}
              </span>

              {/* Actions */}
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => openEdit(cam)}
                  className="p-2 rounded text-ink-muted hover:text-ink-primary hover:bg-surface-600 transition-colors"
                  title="Edit"
                >
                  <Pencil size={14} />
                </button>
                {deleteId === cam.id ? (
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => deleteMutation.mutate(cam.id)}
                      className="text-xs font-mono text-severity-high border border-severity-high/30 px-2 py-1 rounded hover:bg-severity-high-dim transition-colors"
                    >
                      Confirm
                    </button>
                    <button
                      onClick={() => setDeleteId(null)}
                      className="text-xs font-mono text-ink-muted px-2 py-1 rounded hover:bg-surface-600 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setDeleteId(cam.id)}
                    className="p-2 rounded text-ink-muted hover:text-severity-high hover:bg-severity-high-dim transition-colors"
                    title="Delete"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
