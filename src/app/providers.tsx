"use client";

import React, {
  createContext,
  startTransition,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useAuth } from "@/app/auth";
import {
  fetchBootstrap,
  fetchSources,
  getApiBaseUrl,
  patchIncidentAction,
} from "@/lib/api";
import { BUILDINGS, generateEvents } from "@/lib/mockData";
import {
  BackendStatus,
  Building,
  CameraRecord,
  EventRecord,
  RuntimeSummary,
  SourceRecord,
  TimeRange,
} from "@/lib/types";

export type SmartOpsContextValue = {
  events: EventRecord[];
  buildings: Building[];
  cameras: CameraRecord[];
  sources: SourceRecord[];
  refreshSources: () => Promise<void>;
  runtime: RuntimeSummary | null;
  backendStatus: BackendStatus;
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

export const SmartOpsProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const { token } = useAuth();
  const [events, setEvents] = useState<EventRecord[]>(() => generateEvents());
  const [buildings, setBuildings] = useState<Building[]>(BUILDINGS);
  const [cameras, setCameras] = useState<CameraRecord[]>([]);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [runtime, setRuntime] = useState<RuntimeSummary | null>(null);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("fallback");
  const [selectedBuildingId, setSelectedBuildingId] = useState(
    BUILDINGS[0].id
  );
  const [timeRange, setTimeRange] = useState<TimeRange>("7d");
  const [searchQuery, setSearchQuery] = useState("");

  const updateEvent = useCallback(
    (id: string, updater: (event: EventRecord) => EventRecord) => {
      setEvents((prev) =>
        prev.map((event) => (event.id === id ? updater(event) : event))
      );
    },
    []
  );

  const replaceEvent = useCallback((nextEvent: EventRecord) => {
    setEvents((prev) =>
      prev.map((event) => (event.id === nextEvent.id ? nextEvent : event))
    );
  }, []);

  useEffect(() => {
    let active = true;

    const hydrate = async () => {
      if (!token) {
        if (active) setBackendStatus("fallback");
        return;
      }
      try {
        const bootstrap = await fetchBootstrap();

        if (!active) return;

        startTransition(() => {
          setBackendStatus("connected");
          setBuildings(bootstrap.buildings);
          setCameras(bootstrap.cameras);
          setSources(bootstrap.sources ?? []);
          setRuntime(bootstrap.runtime);
          setEvents(bootstrap.incidents);
          if (bootstrap.buildings.length > 0) {
            setSelectedBuildingId((current) =>
              bootstrap.buildings.some((building) => building.id === current)
                ? current
                : bootstrap.buildings[0].id
            );
          }
        });
      } catch {
        if (!active) return;
        setBackendStatus("fallback");
      }
    };

    void hydrate();

    return () => {
      active = false;
    };
  }, [token]);

  useEffect(() => {
    if (typeof window === "undefined" || !token) return;

    const stream = new EventSource(
      `${getApiBaseUrl()}/v1/incidents/stream?token=${encodeURIComponent(token)}`
    );

    stream.addEventListener("snapshot", (event) => {
      try {
        const snapshot = JSON.parse(event.data) as {
          incidents: EventRecord[];
          sources: SourceRecord[];
        };
        startTransition(() => {
          setBackendStatus("connected");
          setEvents(snapshot.incidents);
          setSources(snapshot.sources ?? []);
        });
      } catch {
        // Ignore malformed snapshot; REST hydration remains authoritative.
      }
    });

    stream.addEventListener("incident", (event) => {
      try {
        const incident = JSON.parse(event.data) as EventRecord;
        startTransition(() => {
          setBackendStatus("connected");
          setEvents((prev) => {
            const exists = prev.some((item) => item.id === incident.id);
            return exists
              ? prev.map((item) => (item.id === incident.id ? incident : item))
              : [incident, ...prev];
          });
        });
      } catch {
        // Ignore malformed event payloads.
      }
    });

    stream.addEventListener("source", (event) => {
      try {
        const source = JSON.parse(event.data) as SourceRecord;
        startTransition(() => {
          setSources((prev) => {
            const exists = prev.some((item) => item.id === source.id);
            return exists
              ? prev.map((item) => (item.id === source.id ? source : item))
              : [...prev, source];
          });
        });
      } catch {
        // Ignore malformed event payloads.
      }
    });

    stream.onerror = () => {
      setBackendStatus((current) =>
        current === "connected" ? "connected" : "fallback"
      );
    };

    return () => {
      stream.close();
    };
  }, [token]);

  const refreshSources = useCallback(async () => {
    try {
      const next = await fetchSources();
      setSources(next);
      setBackendStatus("connected");
    } catch {
      // Keep the last known sources; the caller surfaces errors.
    }
  }, []);

  const acknowledgeEvent = useCallback(
    (id: string) => {
      const fallback = () =>
        updateEvent(id, (event) => ({
          ...event,
          status: "acknowledged",
          ackTime: event.ackTime ?? new Date().toISOString(),
        }));

      if (backendStatus === "connected") {
        void patchIncidentAction(id, "acknowledge")
          .then(replaceEvent)
          .catch(fallback);
        return;
      }

      fallback();
    },
    [backendStatus, replaceEvent, updateEvent]
  );

  const assignEvent = useCallback(
    (id: string, assignee = "SmartOps Dispatch") => {
      const fallback = () =>
        updateEvent(id, (event) => ({
          ...event,
          status: "assigned",
          assignedTo: assignee,
          ackTime: event.ackTime ?? new Date().toISOString(),
        }));

      if (backendStatus === "connected") {
        void patchIncidentAction(id, "assign", assignee)
          .then(replaceEvent)
          .catch(fallback);
        return;
      }

      fallback();
    },
    [backendStatus, replaceEvent, updateEvent]
  );

  const resolveEvent = useCallback(
    (id: string) => {
      const fallback = () =>
        updateEvent(id, (event) => ({
          ...event,
          status: "resolved",
          endTime: event.endTime ?? new Date().toISOString(),
          resolvedTime: new Date().toISOString(),
        }));

      if (backendStatus === "connected") {
        void patchIncidentAction(id, "resolve")
          .then(replaceEvent)
          .catch(fallback);
        return;
      }

      fallback();
    },
    [backendStatus, replaceEvent, updateEvent]
  );

  const markFalsePositive = useCallback(
    (id: string) => {
      const fallback = () =>
        updateEvent(id, (event) => ({
          ...event,
          status: "false_positive",
          endTime: new Date().toISOString(),
          resolvedTime: new Date().toISOString(),
        }));

      if (backendStatus === "connected") {
        void patchIncidentAction(id, "false-positive")
          .then(replaceEvent)
          .catch(fallback);
        return;
      }

      fallback();
    },
    [backendStatus, replaceEvent, updateEvent]
  );

  const value = useMemo(
    () => ({
      events,
      buildings,
      cameras,
      sources,
      refreshSources,
      runtime,
      backendStatus,
      selectedBuildingId,
      setSelectedBuildingId,
      timeRange,
      setTimeRange,
      searchQuery,
      setSearchQuery,
      acknowledgeEvent,
      assignEvent,
      resolveEvent,
      markFalsePositive,
    }),
    [
      events,
      buildings,
      cameras,
      sources,
      refreshSources,
      runtime,
      backendStatus,
      selectedBuildingId,
      timeRange,
      searchQuery,
      acknowledgeEvent,
      assignEvent,
      resolveEvent,
      markFalsePositive,
    ]
  );

  return (
    <SmartOpsContext.Provider value={value}>
      {children}
    </SmartOpsContext.Provider>
  );
};

export const useSmartOps = () => {
  const context = useContext(SmartOpsContext);
  if (!context) {
    throw new Error("useSmartOps must be used within SmartOpsProvider");
  }
  return context;
};
