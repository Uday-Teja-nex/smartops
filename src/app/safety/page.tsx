"use client";

import { useMemo } from "react";
import { AlertTriangle, DoorOpen, Flame } from "lucide-react";
import { ChartCard } from "@/components/ChartCard";
import { KpiCard } from "@/components/KpiCard";
import { SectionHeader } from "@/components/SectionHeader";
import { HeatmapGrid } from "@/components/charts/HeatmapGrid";
import { DonutChart } from "@/components/charts/DonutChart";
import { LineTrendChart } from "@/components/charts/LineTrendChart";
import { StatusPill } from "@/components/StatusPill";
import { useSmartOps } from "@/app/providers";
import {
  buildTrend,
  filterEventsByRange,
  getActiveEvents,
  getHotspots,
} from "@/lib/analytics";
import { formatDateTime } from "@/lib/utils";
import { SEVERITY_COLORS } from "@/lib/visuals";

export default function SafetyPage() {
  const { events, selectedBuildingId, timeRange } = useSmartOps();

  const buildingEvents = useMemo(
    () => events.filter((event) => event.buildingId === selectedBuildingId),
    [events, selectedBuildingId]
  );
  const rangeEvents = useMemo(
    () => filterEventsByRange(buildingEvents, timeRange),
    [buildingEvents, timeRange]
  );
  const safetyEvents = useMemo(
    () => rangeEvents.filter((event) => event.category === "Safety"),
    [rangeEvents]
  );
  const activeSafety = useMemo(
    () => getActiveEvents(safetyEvents),
    [safetyEvents]
  );
  const trend = useMemo(() => buildTrend(safetyEvents), [safetyEvents]);
  const hotspots = useMemo(() => getHotspots(safetyEvents, 8), [safetyEvents]);

  const blockedExits = safetyEvents.filter(
    (event) => event.type === "exit_blocked" && event.status !== "resolved"
  ).length;
  const obstructedEquipment = safetyEvents.filter(
    (event) =>
      event.type === "fire_equipment_obstructed" && event.status !== "resolved"
  ).length;
  const slipTrip = safetyEvents.filter(
    (event) =>
      ["slip_trip_hazard", "wet_floor_no_sign", "fallen_object"].includes(
        event.type
      ) && event.status !== "resolved"
  ).length;

  const hazardCounts = useMemo(() => {
    const counts = {
      "Exit blocked": 0,
      "Fire equipment": 0,
      "Wet floor": 0,
      "Fallen object": 0,
      "Slip/trip": 0,
    };
    safetyEvents.forEach((event) => {
      if (event.type === "exit_blocked") counts["Exit blocked"] += 1;
      if (event.type === "fire_equipment_obstructed") counts["Fire equipment"] += 1;
      if (event.type === "wet_floor_no_sign") counts["Wet floor"] += 1;
      if (event.type === "fallen_object") counts["Fallen object"] += 1;
      if (event.type === "slip_trip_hazard") counts["Slip/trip"] += 1;
    });
    return Object.entries(counts).map(([name, value]) => ({
      name,
      value,
      color: SEVERITY_COLORS.high,
    }));
  }, [safetyEvents]);

  const slipTripTrend = useMemo(() => {
    const slipEvents = safetyEvents.filter((event) =>
      ["slip_trip_hazard", "wet_floor_no_sign", "fallen_object"].includes(event.type)
    );
    return buildTrend(slipEvents).map((entry) => entry.count);
  }, [safetyEvents]);

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Safety & EHS
        </p>
        <h1 className="text-3xl font-semibold text-slate-100">
          Safety compliance pulse
        </h1>
        <p className="text-sm text-slate-400">
          All signals are privacy-safe and derived from public/common areas only.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <KpiCard
          title="Emergency exits"
          value={blockedExits ? `${blockedExits} blocked` : "Clear"}
          subtitle="Egress routes monitored"
          status={blockedExits ? "red" : "green"}
          icon={<DoorOpen className="h-4 w-4" aria-hidden />}
          delta={{
            value: blockedExits ? "High risk" : "All clear",
            direction: blockedExits ? "down" : "up",
          }}
        />
        <KpiCard
          title="Fire equipment"
          value={obstructedEquipment ? `${obstructedEquipment} obstructed` : "Accessible"}
          subtitle="AED/extinguisher access"
          status={obstructedEquipment ? "amber" : "green"}
          icon={<Flame className="h-4 w-4" aria-hidden />}
          delta={{
            value: obstructedEquipment ? "Review needed" : "Compliant",
            direction: obstructedEquipment ? "down" : "flat",
          }}
        />
        <KpiCard
          title="Slip/trip hazards"
          value={`${slipTrip}`}
          subtitle="Active hazards"
          status={slipTrip ? "amber" : "green"}
          icon={<AlertTriangle className="h-4 w-4" aria-hidden />}
          sparkline={{ data: slipTripTrend, color: "#f97316" }}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard
          title="Hazards by type"
          subtitle="Signals within range"
          footer={
            <div className="flex flex-wrap gap-2 text-xs text-slate-400">
              {hazardCounts.map((entry) => (
                <span key={entry.name} className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
                  {entry.name} ({entry.value})
                </span>
              ))}
            </div>
          }
        >
          <DonutChart data={hazardCounts} />
        </ChartCard>

        <ChartCard title="7-day trend" subtitle="Safety signals" className="lg:col-span-2">
          <LineTrendChart
            data={trend.map((entry) => ({ name: entry.day, count: entry.count }))}
            lines={[{ key: "count", color: "#e11d48", label: "Safety" }]}
          />
        </ChartCard>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/90 p-5 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.45)] lg:col-span-2">
          <SectionHeader
            title="Active hazards"
            subtitle="Sorted by newest signal"
          />
          <div className="mt-4 space-y-3">
            {activeSafety.slice(0, 6).map((event) => (
              <div
                key={event.id}
                className="rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-2)]/70 px-4 py-3"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-100">
                      {event.shortSummary}
                    </p>
                    <p className="text-xs text-slate-400">
                      {event.zone} - {formatDateTime(event.startTime)}
                    </p>
                  </div>
                  <StatusPill status={event.status} />
                </div>
              </div>
            ))}
            {!activeSafety.length ? (
              <p className="text-sm text-slate-400">No active safety alerts.</p>
            ) : null}
          </div>
        </div>

        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/90 p-5 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.45)]">
          <SectionHeader title="Hotspot heatmap" subtitle="Repeat signals" />
          <div className="mt-4">
            <HeatmapGrid
              items={hotspots.map((spot) => ({ label: spot.zone, value: spot.count }))}
              accent="#e11d48"
              columns={2}
            />
          </div>
        </div>
      </div>
    </div>
  );
}






