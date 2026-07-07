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

const request = async <T,>(path: string, init?: RequestInit): Promise<T> => {
  const token = getStoredToken();
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = `API request failed: ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = `${detail} — ${body.detail}`;
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

export const fetchMe = () => request<UserRecord>("/v1/auth/me", { cache: "no-store" });

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

/**
 * Direct URL for a local file-source clip. The JWT rides as a query param
 * because <video> elements cannot send Authorization headers.
 */
export const getSourceClipUrl = (sourceId: string) => {
  const token = getStoredToken();
  return `${getApiBaseUrl()}/v1/sources/${sourceId}/clip${
    token ? `?token=${encodeURIComponent(token)}` : ""
  }`;
};

// ---------------------------------------------------------------------------
// Pipeline
// ---------------------------------------------------------------------------

export const fetchPipelineStatus = () =>
  request<PipelineStatus>("/v1/pipeline/status", { cache: "no-store" });

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
