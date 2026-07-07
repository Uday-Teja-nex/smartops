import { EventCategory, EventSeverity } from "@/lib/types";

export const CATEGORY_COLORS: Record<EventCategory, string> = {
  Safety: "#e11d48",
  Housekeeping: "#10b981",
  Occupancy: "#6366f1",
  Security: "#f59e0b",
  "Queue & Crowd": "#0ea5e9",
  "System Health": "#a78bfa",
};

export const SEVERITY_COLORS: Record<EventSeverity, string> = {
  low: "#64748b",
  medium: "#f59e0b",
  high: "#f97316",
  critical: "#dc2626",
};

export const STATUS_COLORS: Record<string, string> = {
  active: "#e11d48",
  acknowledged: "#f59e0b",
  assigned: "#0ea5e9",
  in_progress: "#38bdf8",
  resolved: "#10b981",
  false_positive: "#94a3b8",
  escalated: "#fb7185",
  human_review: "#c084fc",
};

export const SOURCE_STATUS_COLORS: Record<string, string> = {
  online: "#10b981",
  processing: "#38bdf8",
  paused: "#f59e0b",
  failing: "#fb7185",
  offline: "#64748b",
};

export const hexToRgba = (hex: string, alpha: number) => {
  const normalized = hex.replace("#", "");
  const bigint = parseInt(normalized, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

export const getCategoryStyle = (category: EventCategory) => ({
  backgroundColor: hexToRgba(CATEGORY_COLORS[category], 0.15),
  color: CATEGORY_COLORS[category],
});

export const getSeverityStyle = (severity: EventSeverity) => ({
  backgroundColor: hexToRgba(SEVERITY_COLORS[severity], 0.15),
  color: SEVERITY_COLORS[severity],
});




