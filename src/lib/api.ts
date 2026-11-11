import {
  BackendBootstrapResponse,
  Building,
  EventRecord,
  IncidentDetail,
  LoginResponse,
  PipelineStatus,
  SourceCreateInput,
  SourceRecord,
  SourceUpdateInput,
  UserRecord,
} from "@/lib/types";

const DEFAULT_API_BASE_URL = "http://localhost:8000";
const TOKEN_STORAGE_KEY = "smartops.token";

export const getApiBaseUrl = () =>
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  DEFAULT_API_BASE_URL;

export const getStoredToken = (): string | null => {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
};

export const setStoredToken = (token: string) => {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
};

export const clearStoredToken = () => {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_STORAGE_KEY);
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export const describeLoginError = (error: unknown): string => {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Invalid email or password.";
    if (error.status === 429) return "Too many sign-in attempts. Wait a minute before trying again.";
    if (error.status === 503) return "Sign-in is temporarily unavailable. Please try again shortly.";
    return "Sign-in failed. Please try again or contact your administrator.";
  }
  return "Could not reach the SmartOps API. Check your connection and try again.";
};

export const describeApiDetail = (detail: unknown): string => {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail)) return "Request could not be validated";
  return detail.slice(0, 5).map((error: { loc?: unknown[]; msg?: unknown }) => {
    const location = Array.isArray(error?.loc) ? error.loc.filter((part) => part !== "body").join(".") : "";
    const message = typeof error?.msg === "string" ? error.msg : "Invalid value";
    return location ? `${location}: ${message}` : message;
  }).join("; ");
};

export const SIGNED_OUT_EVENT = "smartops:signed-out";

const AUTH_SESSION_PATHS = new Set(["/v1/auth/login", "/v1/auth/refresh", "/v1/auth/logout"]);
let refreshInFlight: Promise<string | null> | null = null;

/**
 * Exchange the HttpOnly refresh cookie for a new short-lived access token.
 * Concurrent callers share one request because each refresh rotates the
 * cookie; a second parallel refresh would look like token replay.
 * Returns null when the session is over (explicit 401). Network failures
 * throw so callers can show an offline state instead of signing out.
 */
export const refreshSession = (): Promise<string | null> => {
  refreshInFlight ??= (async () => {
    try {
      const response = await fetch(`${getApiBaseUrl()}/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
        cache: "no-store",
        signal: AbortSignal.timeout(10000),
      });
      if (response.status === 401) {
        clearStoredToken();
        if (typeof window !== "undefined") window.dispatchEvent(new Event(SIGNED_OUT_EVENT));
        return null;
      }
      if (!response.ok) throw new ApiError(`Session refresh failed: ${response.status}`, response.status);
      const body = (await response.json()) as LoginResponse;
      setStoredToken(body.token);
      return body.token;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
};

const send = (path: string, init: RequestInit | undefined, token: string | null) =>
  fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    credentials: AUTH_SESSION_PATHS.has(path) ? "include" : init?.credentials,
    signal: init?.signal ?? AbortSignal.timeout(10000),
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });

const request = async <T,>(path: string, init?: RequestInit): Promise<T> => {
  let response = await send(path, init, getStoredToken());
  if (response.status === 401 && !AUTH_SESSION_PATHS.has(path)) {
    const refreshed = await refreshSession();
    if (refreshed) response = await send(path, init, refreshed);
  }

  if (!response.ok) {
    let detail = `API request failed: ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (body.detail) detail = `${detail} — ${describeApiDetail(body.detail)}`;
    } catch {
      // Non-JSON error body; keep the status-only message.
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
};

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export const login = (email: string, password: string) =>
  request<LoginResponse>("/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

/** Revoke this browser's server session; local sign-out proceeds regardless. */
export const logoutSession = async () => {
  try {
    await request<void>("/v1/auth/logout", { method: "POST", cache: "no-store" });
  } catch {
    // The API may be offline; the access token expires within minutes anyway.
  }
};

export const fetchStreamTicket = () =>
  request<{ ticket: string; expiresInSeconds: number }>("/v1/auth/stream-ticket", {
    method: "POST",
    cache: "no-store",
  });

export const fetchMe = () => request<UserRecord>("/v1/auth/me", { cache: "no-store" });

export const fetchSourcePlayback = (sourceId: string) =>
  request<{ whepUrl: string }>(`/v1/sources/${encodeURIComponent(sourceId)}/playback`, { cache: "no-store" });

export const fetchUsers = () => request<UserRecord[]>("/v1/users", { cache: "no-store" });

export const fetchBootstrap = () =>
  request<BackendBootstrapResponse>("/v1/bootstrap", { cache: "no-store" });

export const fetchBuildings = () =>
  request<Building[]>("/v1/buildings", { cache: "no-store" });

// ---------------------------------------------------------------------------
// Sources
// ---------------------------------------------------------------------------

export const fetchSources = () =>
  request<SourceRecord[]>("/v1/sources", { cache: "no-store" });

export const createSource = (input: SourceCreateInput) =>
  request<SourceRecord>("/v1/sources", {
    method: "POST",
    body: JSON.stringify(input),
  });

export const updateSource = (sourceId: string, input: SourceUpdateInput) =>
  request<SourceRecord>(`/v1/sources/${sourceId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });

export const deleteSource = (sourceId: string) =>
  request<void>(`/v1/sources/${sourceId}`, { method: "DELETE" });

export const sourceAction = (
  sourceId: string,
  action: "pause" | "resume" | "disable"
) =>
  request<SourceRecord>(`/v1/sources/${sourceId}/${action}`, {
    method: "POST",
    body: JSON.stringify({}),
  });

// ---------------------------------------------------------------------------
// Incidents
// ---------------------------------------------------------------------------

export const fetchIncidentDetail = (incidentId: string) =>
  request<IncidentDetail>(`/v1/incidents/${incidentId}`, { cache: "no-store" });

export const patchIncidentAction = (
  incidentId: string,
  action: "acknowledge" | "assign" | "resolve" | "false-positive",
  assignee?: string
) =>
  request<EventRecord>(`/v1/incidents/${incidentId}/${action}`, {
    method: "PATCH",
    body: JSON.stringify(assignee ? { assignee } : {}),
  });

export const updateIncidentStatus = (
  incidentId: string,
  status: string,
  note?: string
) =>
  request<EventRecord>(`/v1/incidents/${incidentId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status, note }),
  });

export const addIncidentComment = (incidentId: string, body: string) =>
  request<{ id: string }>(`/v1/incidents/${incidentId}/comments`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });

// ---------------------------------------------------------------------------
// Evidence
// ---------------------------------------------------------------------------

export const fetchEvidenceUrl = (evidenceId: string) =>
  request<{ id: string; url: string; expiresInSeconds: number }>(
    `/v1/evidence/${evidenceId}/url`,
    { cache: "no-store" }
  );

// ---------------------------------------------------------------------------
// Pipeline
// ---------------------------------------------------------------------------

export const fetchPipelineStatus = () =>
  request<PipelineStatus>("/v1/pipeline/status", { cache: "no-store" });

export type IncidentReport = {
  start: string; end: string; timezone: string; buildingId: string | null;
  totalIncidents: number; categories: Record<string, number>; types: Record<string, number>;
  statuses: Record<string, number>; daily: { date: string; count: number }[];
  acknowledgedCount: number; resolvedTimeCount: number;
  averageAckMinutes: number | null; averageResolveMinutes: number | null;
  completionRate: number | null; falsePositiveRate: number | null;
};

export const fetchIncidentReport = (start: string, end: string, buildingId: string) =>
  request<IncidentReport>(`/v1/reports/summary?${new URLSearchParams({ start, end, buildingId })}`, { cache: "no-store" });

// ---------------------------------------------------------------------------
// Organization / runtime config
// ---------------------------------------------------------------------------

export type OrgInfo = {
  id: string;
  name: string;
  slug: string;
  settings: Record<string, unknown>;
};

export type RuntimeConfig = {
  modelProvider: string;
  orchestrator: string;
  evidenceStorageEnabled: boolean;
  evidenceUrlTtlSeconds: number;
};

export const fetchOrg = () => request<OrgInfo>("/v1/org", { cache: "no-store" });

export const updateOrgSettings = (settings: Record<string, unknown>) =>
  request<OrgInfo>("/v1/org/settings", {
    method: "PUT",
    body: JSON.stringify({ settings }),
  });

export const fetchRuntimeConfig = () =>
  request<RuntimeConfig>("/v1/config", { cache: "no-store" });

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------

export type NotificationSeverity = "low" | "medium" | "high" | "critical";

export type NotificationChannel = {
  id: string;
  kind: "telegram" | "webhook";
  name: string;
  enabled: boolean;
  minSeverity: NotificationSeverity;
  categories: string[];
  activeHours: { start: string; end: string; timezone: string } | null;
  destination: string;
  configured: string[];
  createdAt: string;
  updatedAt: string;
};

export type NotificationChannelInput = {
  kind: "telegram" | "webhook";
  name: string;
  minSeverity: NotificationSeverity;
  categories: string[];
  activeHours: { start: string; end: string; timezone: string } | null;
  config: Record<string, string>;
};

export type NotificationDelivery = {
  id: string;
  incidentId: string | null;
  channelId: string;
  status: "pending" | "sent" | "dead";
  attempts: number;
  lastError: string | null;
  createdAt: string;
  sentAt: string | null;
};

export const fetchNotificationChannels = () =>
  request<NotificationChannel[]>("/v1/notifications/channels", { cache: "no-store" });

export const createNotificationChannel = (input: NotificationChannelInput) =>
  request<NotificationChannel>("/v1/notifications/channels", { method: "POST", body: JSON.stringify(input) });

export const updateNotificationChannel = (id: string, input: Partial<NotificationChannelInput> & { enabled?: boolean }) =>
  request<NotificationChannel>(`/v1/notifications/channels/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });

export const deleteNotificationChannel = (id: string) =>
  request<void>(`/v1/notifications/channels/${encodeURIComponent(id)}`, { method: "DELETE" });

export const testNotificationChannel = (id: string) =>
  request<{ delivered: boolean; error: string | null }>(
    `/v1/notifications/channels/${encodeURIComponent(id)}/test`,
    { method: "POST", signal: AbortSignal.timeout(20000) },
  );

export const fetchNotificationDeliveries = () =>
  request<NotificationDelivery[]>("/v1/notifications/deliveries", { cache: "no-store" });

// ---------------------------------------------------------------------------
// System status
// ---------------------------------------------------------------------------

export type SystemComponent = {
  id: string;
  label: string;
  ok: boolean;
  detail: string;
  impact: string | null;
};

export type SystemStatus = { ok: boolean; checkedAt: string; components: SystemComponent[] };

export const fetchSystemStatus = () =>
  request<SystemStatus>("/v1/system/status", { cache: "no-store", signal: AbortSignal.timeout(8000) });

export type ServiceMetrics = {
  error?: string;
  p50Seconds?: number | null;
  p95Seconds?: number | null;
  outcomes?: Record<string, number> | null;
};
export type SystemMetrics = { checkedAt: string; minSamples: number; scope: string; detector: ServiceMetrics; ai: ServiceMetrics };

/** Latency percentiles and outcome shares scraped from the shared services' /metrics. */
export const fetchSystemMetrics = () =>
  request<SystemMetrics>("/v1/system/metrics", { cache: "no-store", signal: AbortSignal.timeout(8000) });

export type PhoneCameraResult = {
  source: SourceRecord;
  publish: { rtmpUrl: string; server: string; streamKey: string; path: string; lanHostConfigured: boolean };
};

export const createPhoneCamera = (input: {
  name: string; buildingId: string; floorId?: string; zoneId?: string;
}) =>
  request<PhoneCameraResult>("/v1/sources/phone", { method: "POST", body: JSON.stringify(input) });

// ---------------------------------------------------------------------------
// Client workspaces (platform admins)
// ---------------------------------------------------------------------------

export type WorkspaceCapabilities = {
  canCreateWorkspaces: boolean;
  copyableCameras: { id: string; name: string; workspace: string; zones: number }[];
};

export type WorkspaceInput = {
  name: string;
  accent: string;
  buildingName: string;
  address?: string;
  timezone?: string;
  floors: { level: string; name: string; zones: string[] }[];
  password: string;
  copyCameraId?: string;
  addPhoneCamera: boolean;
};

export type WorkspaceCreated = {
  id: string;
  name: string;
  accounts: { email: string; role: string }[];
  cameras: string[];
};

export const fetchWorkspaceCapabilities = () =>
  request<WorkspaceCapabilities>("/v1/workspaces/capabilities", { cache: "no-store" });

export const createWorkspace = (input: WorkspaceInput) =>
  request<WorkspaceCreated>("/v1/workspaces", { method: "POST", body: JSON.stringify(input) });

// ---------------------------------------------------------------------------
// User management
// ---------------------------------------------------------------------------

export const inviteUser = (input: { email: string; name: string; role: UserRecord["role"] }) =>
  request<{ user: UserRecord; temporaryPassword: string }>("/v1/users", { method: "POST", body: JSON.stringify(input) });

export const updateUser = (id: string, input: { name?: string; role?: UserRecord["role"]; active?: boolean }) =>
  request<UserRecord>(`/v1/users/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(input) });

export const resetUserPassword = (id: string) =>
  request<{ temporaryPassword: string }>(`/v1/users/${encodeURIComponent(id)}/reset-password`, { method: "POST" });

export const changeOwnPassword = (currentPassword: string, newPassword: string) =>
  request<void>("/v1/auth/password", { method: "POST", body: JSON.stringify({ currentPassword, newPassword }) });
