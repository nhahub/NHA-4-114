import axios from "axios";
import type {
  Camera,
  CameraCreate,
  Alert,
  AlertSeverity,
  AnalyticsSummary,
  HeatmapData,
  Zone,
  ZoneCreate,
  ZoneStats,
  EventLog,
  EventType,
  HealthStatus,
  PaginatedResponse,
} from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const client = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 10_000,
});

import { getToken, clearToken } from "@/lib/auth";

client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      clearToken();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export const apiClient = {
  getCameras: () => client.get<Camera[]>('/cameras').then((r) => r.data),
  getZones: (cameraId: number) =>
    client
      .get<Zone[]>('/zones', { params: { camera_id: cameraId } })
      .then((r) => r.data),
  createZone: (payload: ZoneCreate) =>
    client.post<Zone>('/zones', payload).then((r) => r.data),
  updateZone: (id: number, payload: Partial<ZoneCreate>) =>
    client.put<Zone>(`/zones/${id}`, payload).then((r) => r.data),
  deleteZone: (id: number) => client.delete(`/zones/${id}`).then((r) => r.data),
};

// ─── Cameras ────────────────────────────────────────────────────────────────

export const camerasApi = {
  list: () =>
    client.get<Camera[]>('/cameras').then((r) => r.data),

  get: (id: number) =>
    client.get<Camera>(`/cameras/${id}`).then((r) => r.data),

  create: (payload: CameraCreate) =>
    client.post<Camera>('/cameras', payload).then((r) => r.data),

  update: (id: number, payload: Partial<CameraCreate>) =>
    client.put<Camera>(`/cameras/${id}`, payload).then((r) => r.data),

  delete: (id: number) =>
    client.delete(`/cameras/${id}`).then((r) => r.data),
};

// ─── Alerts ─────────────────────────────────────────────────────────────────

export interface AlertsQuery {
  page?: number;
  limit?: number;
  severity?: AlertSeverity;
  camera_id?: number;
}

export const alertsApi = {
  list: (params: AlertsQuery = {}) =>
    client
      .get<PaginatedResponse<Alert>>('/alerts', { params })
      .then((r) => r.data),

  get: (id: number) =>
    client.get<Alert>(`/alerts/${id}`).then((r) => r.data),
};

// ─── Analytics ──────────────────────────────────────────────────────────────

export const analyticsApi = {
  summary: () =>
    client.get<AnalyticsSummary>('/analytics/summary').then((r) => r.data),

  heatmap: (cameraId: number) =>
    client
      .get<HeatmapData>(`/analytics/heatmap/${cameraId}`)
      .then((r) => r.data),

  zones: (cameraId: number) =>
    client
      .get<ZoneStats>(`/analytics/zones/${cameraId}`)
      .then((r) => r.data),
};

// ─── Logs ───────────────────────────────────────────────────────────────────

export interface LogsQuery {
  camera_id?: number;
  event_type?: EventType;
  page?: number;
  limit?: number;
}

export const logsApi = {
  list: (params: LogsQuery = {}) =>
    client
      .get<PaginatedResponse<EventLog>>('/logs', { params })
      .then((r) => r.data),
};

// ─── Health ─────────────────────────────────────────────────────────────────

export const healthApi = {
  check: () =>
    client.get<HealthStatus>('/health').then((r) => r.data),
};
