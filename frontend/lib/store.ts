import { create } from "zustand";
import type { WSCameraFrame, WSAlert, Camera, ConnectionStatus } from "@/types";

// ─── Camera Stream Store ─────────────────────────────────────────────────────

interface CameraStreamState {
  frame: WSCameraFrame | null;
  status: ConnectionStatus;
  setFrame: (frame: WSCameraFrame) => void;
  setStatus: (status: ConnectionStatus) => void;
  reset: () => void;
}

export const useCameraStreamStore = create<CameraStreamState>((set) => ({
  frame: null,
  status: "disconnected",
  setFrame: (frame) => set({ frame }),
  setStatus: (status) => set({ status }),
  reset: () => set({ frame: null, status: "disconnected" }),
}));

// ─── Alerts Store ────────────────────────────────────────────────────────────

const MAX_LIVE_ALERTS = 50;

interface AlertsState {
  liveAlerts: WSAlert[];
  alertStatus: ConnectionStatus;
  pushAlert: (alert: WSAlert) => void;
  clearAlerts: () => void;
  setAlertStatus: (status: ConnectionStatus) => void;
}

export const useAlertsStore = create<AlertsState>((set) => ({
  liveAlerts: [],
  alertStatus: "disconnected",
  pushAlert: (alert) =>
    set((state) => ({
      liveAlerts: [alert, ...state.liveAlerts].slice(0, MAX_LIVE_ALERTS),
    })),
  clearAlerts: () => set({ liveAlerts: [] }),
  setAlertStatus: (alertStatus) => set({ alertStatus }),
}));

// ─── Cameras Store ───────────────────────────────────────────────────────────

interface CamerasState {
  cameras: Camera[];
  activeCameraId: number | null;
  setCameras: (cameras: Camera[]) => void;
  setActiveCameraId: (id: number | null) => void;
  addCamera: (camera: Camera) => void;
  updateCamera: (camera: Camera) => void;
  removeCamera: (id: number) => void;
}

export const useCamerasStore = create<CamerasState>((set) => ({
  cameras: [],
  activeCameraId: null,
  setCameras: (cameras) =>
    set({ cameras, activeCameraId: cameras[0]?.id ?? null }),
  setActiveCameraId: (id) => set({ activeCameraId: id }),
  addCamera: (camera) =>
    set((state) => ({ cameras: [...state.cameras, camera] })),
  updateCamera: (camera) =>
    set((state) => ({
      cameras: state.cameras.map((c) => (c.id === camera.id ? camera : c)),
    })),
  removeCamera: (id) =>
    set((state) => ({
      cameras: state.cameras.filter((c) => c.id !== id),
    })),
}));

// ─── UI Store ────────────────────────────────────────────────────────────────

interface UIState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () =>
    set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
}));
