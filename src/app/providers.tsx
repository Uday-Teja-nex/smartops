"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/app/auth";
import { fetchBootstrap, fetchSources, getApiBaseUrl, patchIncidentAction } from "@/lib/api";
import { BackendStatus, Building, EventRecord, LiveObservation, RuntimeSummary, SourceRecord, TimeRange } from "@/lib/types";

export type SmartOpsContextValue = {
  events: EventRecord[];
  observations: Record<string, LiveObservation>;
  buildings: Building[];
  sources: SourceRecord[];
  refreshSources: () => Promise<void>;
  runtime: RuntimeSummary | null;
  backendStatus: BackendStatus;
  actionError: string | null;
  selectedBuildingId: string;
  setSelectedBuildingId: (id: string) => void;
  timeRange: TimeRange;
  setTimeRange: (range: TimeRange) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  acknowledgeEvent: (id: string) => void;
  assignEvent: (id: string, assignee?: string) => void;
  resolveEvent: (id: string) => void;
  markFalsePositive: (id: string) => void;
};

const SmartOpsContext = createContext<SmartOpsContextValue | null>(null);

export const SmartOpsProvider = ({ children }: { children: React.ReactNode }) => {
  const { token } = useAuth();
  // A new session must never inherit the previous workspace's cached rows.
  return <SessionProvider key={token ?? "signed-out"} token={token}>{children}</SessionProvider>;
};

const SessionProvider = ({ children, token }: { children: React.ReactNode; token: string | null }) => {
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [observations, setObservations] = useState<Record<string, LiveObservation>>({});
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [runtime, setRuntime] = useState<RuntimeSummary | null>(null);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("loading");
  const [actionError, setActionError] = useState<string | null>(null);
  const [selectedBuildingId, setSelectedBuildingId] = useState("");
  const [timeRange, setTimeRange] = useState<TimeRange>("7d");
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    if (!token) return;
    let active = true;
    let stream: EventSource | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const hydrate = async () => {
      try {
        const bootstrap = await fetchBootstrap();
        if (!active) return;
        setBuildings(bootstrap.buildings);
        setSources(bootstrap.sources ?? []);
        setRuntime(bootstrap.runtime);
        setEvents(bootstrap.incidents);
        setSelectedBuildingId((current) => bootstrap.buildings.some((b) => b.id === current)
          ? current : bootstrap.buildings[0]?.id ?? "");
        // Start streaming only after bootstrap to avoid a stale REST response
        // overwriting a newer stream event.
        stream = new EventSource(`${getApiBaseUrl()}/v1/incidents/stream?token=${encodeURIComponent(token)}`);
        stream.addEventListener("snapshot", (event) => {
          try {
            const snapshot = JSON.parse(event.data) as { incidents: EventRecord[]; sources: SourceRecord[] };
            if (!active) return;
            setEvents(snapshot.incidents);
            setSources(snapshot.sources ?? []);
            setBackendStatus("connected");
          } catch { setBackendStatus("offline"); }
        });
        stream.addEventListener("incident", (event) => {
          try {
            const incident = JSON.parse(event.data) as EventRecord;
            if (!active) return;
            setEvents((prev) => prev.some((item) => item.id === incident.id)
              ? prev.map((item) => item.id === incident.id ? incident : item) : [incident, ...prev].slice(0, 200));
          } catch { setBackendStatus("offline"); }
        });
        stream.addEventListener("observation", (event) => {
          try {
            const observation = JSON.parse(event.data) as LiveObservation;
            if (!active) return;
            setObservations((previous) => ({
              ...Object.fromEntries(Object.entries(previous).filter(([, item]) =>
                Date.now() - Date.parse(item.capturedAt) < 10000).slice(-63)),
              [observation.sourceId]: observation,
            }));
          } catch { /* A malformed observation must not replace a real frame. */ }
        });
        stream.addEventListener("source", (event) => {
          try {
            const source = JSON.parse(event.data) as SourceRecord;
            if (!active) return;
            setSources((prev) => prev.some((item) => item.id === source.id)
              ? prev.map((item) => item.id === source.id ? source : item) : [...prev, source]);
          } catch { setBackendStatus("offline"); }
        });
        stream.onerror = () => {
          if (!active) return;
          setBackendStatus("offline");
          stream?.close();
          retry = setTimeout(() => void hydrate(), 3000);
        };
      } catch {
        if (!active) return;
        setBackendStatus("offline");
        retry = setTimeout(() => void hydrate(), 3000);
      }
    };
    void hydrate();
    return () => { active = false; stream?.close(); clearTimeout(retry); };
  }, [token]);

  const refreshSources = useCallback(async () => {
    const next = await fetchSources();
    setSources(next);
  }, []);

  const act = useCallback((id: string, action: Parameters<typeof patchIncidentAction>[1], assignee?: string) => {
    setActionError(null);
    if (backendStatus !== "connected") {
      setActionError("Action not saved: the API or live connection is unavailable. Reconnect and try again.");
      return;
    }
    void patchIncidentAction(id, action, assignee).then((next) => {
      setEvents((prev) => prev.map((event) => event.id === next.id ? next : event));
    }).catch((error: unknown) => {
      setActionError(`Action not confirmed: ${error instanceof Error ? error.message : "request failed"}. Reload the incident before retrying.`);
    });
  }, [backendStatus]);
  const acknowledgeEvent = useCallback((id: string) => act(id, "acknowledge"), [act]);
  const assignEvent = useCallback((id: string, assignee?: string) => act(id, "assign", assignee), [act]);
  const resolveEvent = useCallback((id: string) => act(id, "resolve"), [act]);
  const markFalsePositive = useCallback((id: string) => act(id, "false-positive"), [act]);

  const value = useMemo(() => ({ events, observations, buildings, sources, refreshSources, runtime,
    backendStatus, actionError, selectedBuildingId, setSelectedBuildingId, timeRange, setTimeRange,
    searchQuery, setSearchQuery, acknowledgeEvent, assignEvent, resolveEvent, markFalsePositive }),
  [events, observations, buildings, sources, refreshSources, runtime, backendStatus, actionError,
    selectedBuildingId, timeRange, searchQuery, acknowledgeEvent, assignEvent, resolveEvent, markFalsePositive]);
  return <SmartOpsContext.Provider value={value}>{children}</SmartOpsContext.Provider>;
};

export const useSmartOps = () => {
  const context = useContext(SmartOpsContext);
  if (!context) throw new Error("useSmartOps must be used within SmartOpsProvider");
  return context;
};
