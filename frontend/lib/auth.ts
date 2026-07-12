/**
 * lib/auth.ts
 * In-memory token store + axios interceptor.
 * Token is NEVER stored in localStorage — kept in module-level variable.
 * On page refresh the user is redirected to /login (intentional for security).
 */

import axios from "axios";
import { setAuthCookie, clearAuthCookie } from "@/lib/authCookie";

// ---------------------------------------------------------------------------
// In-memory token store
// ---------------------------------------------------------------------------
let _accessToken: string | null = null;
let _expiresAt: number | null = null; // Unix ms

export function setToken(token: string, expiresInSeconds: number): void {
  _accessToken = token;
  _expiresAt = Date.now() + expiresInSeconds * 1000;
}

export function getToken(): string | null {
  if (!_accessToken || !_expiresAt) return null;
  if (Date.now() >= _expiresAt) {
    clearToken();
    return null;
  }
  return _accessToken;
}

export function clearToken(): void {
  _accessToken = null;
  _expiresAt = null;
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

// ---------------------------------------------------------------------------
// HTTP client for auth endpoints (no global 401 redirect on failed login)
// ---------------------------------------------------------------------------
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const authHttp = axios.create({
  baseURL: `${API}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 10_000,
});

// ---------------------------------------------------------------------------
// Axios interceptor — attach Bearer token to every default-axios request
// ---------------------------------------------------------------------------
axios.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

axios.interceptors.response.use(
  (res) => res,
  async (error) => {
    const url = error.config?.url ?? "";
    const isAuthTokenRequest =
      typeof url === "string" && url.includes("/auth/token");

    if (error.response?.status === 401 && !isAuthTokenRequest) {
      clearToken();
      clearAuthCookie();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------
export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

/** POST /api/v1/auth/token — expects JSON body matching backend LoginRequest */
export async function login(username: string, password: string): Promise<void> {
  const { data } = await authHttp.post<LoginResponse>("/auth/token", {
    username: username.trim(),
    password,
  });
  setToken(data.access_token, data.expires_in);
  setAuthCookie();
}

export async function refreshToken(): Promise<void> {
  const { data } = await authHttp.post<LoginResponse>(
    "/auth/refresh",
    {},
    {
      headers: { Authorization: `Bearer ${getToken()}` },
    }
  );
  setToken(data.access_token, data.expires_in);
}

export function logout(): void {
  clearToken();
  clearAuthCookie();
  if (typeof window !== "undefined") {
    window.location.href = "/login";
  }
}

/**
 * Build a WebSocket URL with the current token appended as ?token=<jwt>.
 * Usage: const ws = new WebSocket(wsUrl("/ws/cameras/1"))
 */
export function wsUrl(path: string): string {
  const base = (process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000").replace(
    /\/$/,
    ""
  );
  const token = getToken();
  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${base}${path}${query}`;
}
