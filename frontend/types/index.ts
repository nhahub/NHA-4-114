// ─── Camera ─────────────────────────────────────────────────────────────────

export type SourceType = "rtsp" | "usb" | "file";

export interface Camera {
  id: number;
  name: string;
  source_type: SourceType;
  source_url: string;
  is_active: boolean;
  created_at: string;
}

export interface CameraCreate {
  name: string;
  source_type: SourceType;
  source_url: string;
  is_active: boolean;
}

export interface Zone {
  id: number;
  camera_id: number;
  name: string;
  polygon: [number, number][];
  threshold: number;
  is_active: boolean;
  created_at: string;
}

export interface ZoneCreate {
  camera_id: number;
  name: string;
  polygon: [number, number][];
  threshold: number;
  is_active: boolean;
}

// ─── Alerts ─────────────────────────────────────────────────────────────────

export type AlertSeverity = "high" | "medium" | "low" | "info";

export type AlertType =
  | "zone_overcrowding"
  | "loitering"
  | "crossing_event"
  | "zone_occupancy";

export interface Alert {
  id: number;
  camera_id: number;
  type: AlertType;
  severity: AlertSeverity;
  message: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

export interface PaginatedResponse<T> {
  items: T[];
  page: number;
  limit: number;
  total: number;
}

// ─── Analytics ──────────────────────────────────────────────────────────────

export interface AnalyticsSummary {
  total_in: number;
  total_out: number;
  current_occupancy: number;
  active_alerts: number;
}

export interface HeatmapData {
  camera_id: number;
  heatmap_url: string | null;
}

export interface ZoneStats {
  zones: {
    zone_id: number;
    name: string;
    occupancy: number;
    threshold: number;
  }[];
}

// ─── Logs ───────────────────────────────────────────────────────────────────

export type EventType =
  | "entry_event"
  | "exit_event"
  | "zone_violation"
  | "loitering_alert";

export interface EventLog {
  id: number;
  camera_id: number;
  event_type: EventType;
  message: string;
  timestamp: string;
}

// ─── Health ─────────────────────────────────────────────────────────────────

export interface HealthStatus {
  status: "ok" | "degraded" | "error";
  database: "connected" | "disconnected";
  redis: "connected" | "disconnected";
}

// ─── WebSocket Payloads ──────────────────────────────────────────────────────

export interface Track {
  track_id: number;
  bbox: [number, number, number, number]; // [x1, y1, x2, y2]
}

export interface ZoneOccupancyEvent {
  type: "zone_occupancy" | "zone_overcrowding";
  zone_id: number;
  zone_name: string;
  occupancy: number;
  threshold: number;
  timestamp: number;
}

export interface WSCameraFrame {
  camera_id: number;
  timestamp: string;
  frame: string; // base64 JPEG
  occupancy: number;
  tracks: Track[];
  business_events?: ZoneOccupancyEvent[];
}

export interface WSAlert {
  camera_id: number;
  type: AlertType;
  severity: AlertSeverity;
  message: string;
  timestamp: string;
  metadata?: {
    track_id?: number;
    duration_s?: number;
    position?: [number, number];
    zone_id?: number;
    zone_name?: string;
    occupancy?: number;
    threshold?: number;
    occupant_ids?: number[];
  };
}

// ─── UI Helpers ─────────────────────────────────────────────────────────────

export type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";
