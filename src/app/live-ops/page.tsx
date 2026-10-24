"use client";

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { FiltersBar, AlertFilters } from "@/components/FiltersBar";
import { EventDetailDrawer } from "@/components/EventDetailDrawer";
import { EventTable } from "@/components/EventTable";
import { SectionHeader } from "@/components/SectionHeader";
import { ChartCard } from "@/components/ChartCard";
import { DonutChart } from "@/components/charts/DonutChart";
import { StackedBarChart } from "@/components/charts/StackedBarChart";
import { useSmartOps } from "@/app/providers";
import {
  filterEventsByRange,
  getCountsByCategory,
  getCountsBySeverity,
  getCountsByStatus,
  getHotspots,
  TIME_RANGE_LABELS,
} from "@/lib/analytics";
import { SourceRecord, EventRecord, TimeRange } from "@/lib/types";
import {
  CATEGORY_COLORS,
  SEVERITY_COLORS,
  STATUS_COLORS,
} from "@/lib/visuals";

const defaultFilters: AlertFilters = {
  category: "All",
  severity: "All",
  status: "All",
  floor: "All",
  zone: "All",
};

const buildFiltersFromQuery = (searchParams: URLSearchParams) => {
  const nextFilters = { ...defaultFilters };
  const category = searchParams.get("category");
  const status = searchParams.get("status");
  const severity = searchParams.get("severity");
  const floor = searchParams.get("floor");
  const zone = searchParams.get("zone");

  if (category) nextFilters.category = category;
  if (status) nextFilters.status = status;
  if (severity) nextFilters.severity = severity;
  if (floor) nextFilters.floor = floor;
  if (zone) nextFilters.zone = zone;

  return nextFilters;
};

const LiveOpsContent = ({
  events,
  sources,
  selectedBuildingId,
  timeRange,
  searchQuery,
  initialFilters,
  initialEventId,
  acknowledgeEvent,
  assignEvent,
  resolveEvent,
  markFalsePositive,
}: {
  events: EventRecord[];
  sources: SourceRecord[];
  selectedBuildingId: string;
  timeRange: TimeRange;
  searchQuery: string;
  initialFilters: AlertFilters;
  initialEventId: string | null;
  acknowledgeEvent: (id: string) => void;
  assignEvent: (id: string) => void;
  resolveEvent: (id: string) => void;
  markFalsePositive: (id: string) => void;
}) => {
  const [filters, setFilters] = useState<AlertFilters>(initialFilters);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(
    initialEventId
  );

  const buildingEvents = useMemo(
    () => events.filter((event) => event.buildingId === selectedBuildingId),
    [events, selectedBuildingId]
  );
  const rangeEvents = useMemo(
    () => filterEventsByRange(buildingEvents, timeRange),
    [buildingEvents, timeRange]
  );

  const filteredEvents = useMemo(() => {
    return rangeEvents.filter((event) => {
      if (filters.category !== "All" && event.category !== filters.category) {
        return false;
      }
      if (filters.severity !== "All" && event.severity !== filters.severity) {
        return false;
      }
      if (filters.status !== "All" && event.status !== filters.status) {
        return false;
      }
      if (filters.floor !== "All" && event.floor !== filters.floor) {
        return false;
      }
      if (filters.zone !== "All" && event.zone !== filters.zone) {
        return false;
      }
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        return (
          event.shortSummary.toLowerCase().includes(query) ||
          event.zone.toLowerCase().includes(query) ||
          event.sourceId.toLowerCase().includes(query)
        );
      }
      return true;
    });
  }, [rangeEvents, filters, searchQuery]);

  const countsByCategory = useMemo(
    () => getCountsByCategory(rangeEvents),
    [rangeEvents]
  );
  const countsBySeverity = useMemo(
    () => getCountsBySeverity(rangeEvents),
    [rangeEvents]
  );
  const countsByStatus = useMemo(
    () => getCountsByStatus(rangeEvents),
    [rangeEvents]
  );
  const hotspots = useMemo(() => getHotspots(rangeEvents, 4), [rangeEvents]);

  const categoryChart = useMemo(
    () =>
      Object.entries(countsByCategory).map(([name, value]) => ({
        name,
        value,
        color: CATEGORY_COLORS[name as keyof typeof CATEGORY_COLORS] ?? "#94a3b8",
      })),
    [countsByCategory]
  );

  const statusChart = useMemo(
    () =>
      Object.entries(countsByStatus).map(([name, value]) => ({
        name: name.replace("_", " "),
        value,
        color: STATUS_COLORS[name] ?? "#94a3b8",
      })),
    [countsByStatus]
  );

  const severityStackData = useMemo(
    () => [
      {
        name: "Severity mix",
        low: countsBySeverity.low ?? 0,
        medium: countsBySeverity.medium ?? 0,
        high: countsBySeverity.high ?? 0,
        critical: countsBySeverity.critical ?? 0,
      },
    ],
    [countsBySeverity]
  );

  const hotspotData = useMemo(
    () => hotspots.map((spot) => ({ name: spot.zone, value: spot.count })),
    [hotspots]
  );

  const selectedEvent =
    buildingEvents.find((event) => event.id === selectedEventId) ??
    events.find((event) => event.id === selectedEventId) ??
    null;
  const selectedCamera = selectedEvent
    ? sources.find((camera) => camera.id === selectedEvent.sourceId) ?? null
    : null;
  const relatedEvents = useMemo(() => {
    if (!selectedEvent) return [];
    return buildingEvents
      .filter(
        (event) =>
          event.zone === selectedEvent.zone && event.id !== selectedEvent.id
      )
      .slice(0, 3);
  }, [buildingEvents, selectedEvent]);

  const handleSelect = (event: EventRecord) => {
    setSelectedEventId(event.id);
  };

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Unified Alerts
        </p>
        <h1 className="text-3xl font-semibold text-slate-100">Live Ops</h1>
        <p className="text-sm text-slate-400">
          Filters apply to aggregated events. Evidence is restricted by default.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        <ChartCard
          title="Category mix"
          subtitle="Events by category"
          footer={
            <div className="flex flex-wrap gap-2 text-xs text-slate-400">
              {categoryChart.map((entry) => (
                <span key={entry.name} className="flex items-center gap-2">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: entry.color }}
                  />
                  {entry.name} ({entry.value})
                </span>
              ))}
            </div>
          }
        >
          <DonutChart data={categoryChart} />
        </ChartCard>

        <ChartCard
          title="Severity distribution"
          subtitle="Stacked within range"
          footer={
            <div className="flex flex-wrap gap-2 text-xs text-slate-400">
              {Object.entries(SEVERITY_COLORS).map(([key, color]) => (
                <span key={key} className="flex items-center gap-2 capitalize">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                  {key} ({countsBySeverity[key as keyof typeof countsBySeverity] ?? 0})
                </span>
              ))}
            </div>
          }
        >
          <StackedBarChart
            data={severityStackData}
            series={[
              { key: "low", label: "Low", color: SEVERITY_COLORS.low, stackId: "severity" },
              { key: "medium", label: "Medium", color: SEVERITY_COLORS.medium, stackId: "severity" },
              { key: "high", label: "High", color: SEVERITY_COLORS.high, stackId: "severity" },
              { key: "critical", label: "Critical", color: SEVERITY_COLORS.critical, stackId: "severity" },
            ]}
            layout="vertical"
          />
        </ChartCard>

        <ChartCard
          title="Status mix"
          subtitle={TIME_RANGE_LABELS[timeRange]}
          footer={
            <div className="flex flex-wrap gap-2 text-xs text-slate-400">
              {statusChart.map((entry) => (
                <span key={entry.name} className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
                  {entry.name} ({entry.value})
                </span>
              ))}
            </div>
          }
        >
          <DonutChart data={statusChart} />
        </ChartCard>

        <ChartCard
          title="Hotspots"
          subtitle="Top zones by alerts"
          footer={<span className="text-xs text-slate-400">Top 4 zones</span>}
        >
          <StackedBarChart
            data={hotspotData}
            series={[{ key: "value", label: "Events", color: "#6366f1" }]}
            layout="vertical"
          />
        </ChartCard>
      </div>

      <SectionHeader
        title="Alerts"
        subtitle="Filter by category, severity, status, floor, and zone"
        action={
          <span className="rounded-full bg-[color:var(--surface-2)] px-3 py-1 text-xs font-semibold text-slate-300">
            {TIME_RANGE_LABELS[timeRange]}
          </span>
        }
      />
      <FiltersBar events={rangeEvents} filters={filters} onChange={setFilters} />

      {filteredEvents.length ? (
        <EventTable
          events={filteredEvents}
          onSelect={handleSelect}
          selectedId={selectedEventId}
        />
      ) : (
        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/95 p-6 text-sm text-slate-400 shadow-sm">
          No alerts match the current filters and time range.
        </div>
      )}

      <EventDetailDrawer
        event={selectedEvent}
        open={Boolean(selectedEvent)}
        onClose={() => setSelectedEventId(null)}
        onAcknowledge={() => selectedEvent && acknowledgeEvent(selectedEvent.id)}
        onAssign={() => selectedEvent && assignEvent(selectedEvent.id)}
        onResolve={() => selectedEvent && resolveEvent(selectedEvent.id)}
        onFalsePositive={() =>
          selectedEvent && markFalsePositive(selectedEvent.id)
        }
        relatedEvents={relatedEvents}
        camera={selectedCamera}
      />
    </div>
  );
};

const LiveOpsSearchParams = () => {
  const searchParams = useSearchParams();
  const {
    events,
    sources,
    selectedBuildingId,
    timeRange,
    searchQuery,
    acknowledgeEvent,
    assignEvent,
    resolveEvent,
    markFalsePositive,
  } = useSmartOps();

  const initialFilters = useMemo(
    () => buildFiltersFromQuery(searchParams),
    [searchParams]
  );
  const initialEventId = searchParams.get("event");
  const key = searchParams.toString();

  return (
    <LiveOpsContent
      key={key}
      events={events}
      sources={sources}
      selectedBuildingId={selectedBuildingId}
      timeRange={timeRange}
      searchQuery={searchQuery}
      initialFilters={initialFilters}
      initialEventId={initialEventId}
      acknowledgeEvent={acknowledgeEvent}
      assignEvent={assignEvent}
      resolveEvent={resolveEvent}
      markFalsePositive={markFalsePositive}
    />
  );
};

export default function LiveOpsPage() {
  return (
    <Suspense
      fallback={
        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/95 p-6 text-sm text-slate-400">
          Loading Live Ops...
        </div>
      }
    >
      <LiveOpsSearchParams />
    </Suspense>
  );
}


