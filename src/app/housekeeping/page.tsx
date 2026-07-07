"use client";

import { useMemo } from "react";
import { CheckCircle2, Timer, Sparkles } from "lucide-react";
import { ChartCard } from "@/components/ChartCard";
import { KpiCard } from "@/components/KpiCard";
import { SectionHeader } from "@/components/SectionHeader";
import { HeatmapGrid } from "@/components/charts/HeatmapGrid";
import { DonutChart } from "@/components/charts/DonutChart";
import { LineTrendChart } from "@/components/charts/LineTrendChart";
import { useSmartOps } from "@/app/providers";
import {
  buildTrend,
  filterEventsByRange,
  getActiveEvents,
  getHotspots,
  getSlaMetrics,
} from "@/lib/analytics";
import { CLEANING_COMPLETION } from "@/lib/mockData";
import { formatDateTime, formatDurationMinutes, formatPercent, getNowTimestamp } from "@/lib/utils";

const SERVICE_COLORS = ["#10b981", "#34d399", "#6ee7b7"];

export default function HousekeepingPage() {
  const { events, selectedBuildingId, timeRange } = useSmartOps();

  const buildingEvents = useMemo(
    () => events.filter((event) => event.buildingId === selectedBuildingId),
    [events, selectedBuildingId]
  );
  const rangeEvents = useMemo(
    () => filterEventsByRange(buildingEvents, timeRange),
    [buildingEvents, timeRange]
  );
  const housekeepingEvents = useMemo(
    () => rangeEvents.filter((event) => event.category === "Housekeeping"),
    [rangeEvents]
  );
  const activeHousekeeping = useMemo(
    () => getActiveEvents(housekeepingEvents),
    [housekeepingEvents]
  );
  const slaMetrics = useMemo(
    () => getSlaMetrics(housekeepingEvents),
    [housekeepingEvents]
  );
  const hotspots = useMemo(() => getHotspots(housekeepingEvents, 6), [
    housekeepingEvents,
  ]);

  const completionRate = useMemo(() => {
    const completed = CLEANING_COMPLETION.filter((entry) => entry.completed).length;
    return completed / CLEANING_COMPLETION.length;
  }, []);

  const serviceNeeded = useMemo(
    () =>
      activeHousekeeping.filter((event) =>
        ["restroom_service_needed", "bin_overflow", "litter_hotspot"].includes(event.type)
      ),
    [activeHousekeeping]
  );

  const serviceTypeCounts = useMemo(() => {
    const counts = {
      "Restroom entry": 0,
      "Bin overflow": 0,
      "Litter hotspot": 0,
    };
    serviceNeeded.forEach((event) => {
      if (event.type === "restroom_service_needed") counts["Restroom entry"] += 1;
      if (event.type === "bin_overflow") counts["Bin overflow"] += 1;
      if (event.type === "litter_hotspot") counts["Litter hotspot"] += 1;
    });
    return Object.entries(counts).map(([name, value], index) => ({
      name,
      value,
      color: SERVICE_COLORS[index],
    }));
  }, [serviceNeeded]);

  const completionByFloor = useMemo(() => {
    return CLEANING_COMPLETION.reduce<Record<string, typeof CLEANING_COMPLETION>>(
      (acc, entry) => {
        acc[entry.floor] = acc[entry.floor] || [];
        acc[entry.floor].push(entry);
        return acc;
      },
      {}
    );
  }, []);

  const slaTrend = useMemo(() => {
    const days = new Array(7).fill(0).map((_, index) => ({
      name: `D-${6 - index}`,
      ackSum: 0,
      ackCount: 0,
      resolveSum: 0,
      resolveCount: 0,
    }));
    const now = getNowTimestamp();
    housekeepingEvents.forEach((event) => {
      const diffDays = Math.floor(
        (now - new Date(event.startTime).getTime()) / (24 * 60 * 60 * 1000)
      );
      if (diffDays < 0 || diffDays > 6) return;
      const bucket = days[6 - diffDays];
      if (event.ackTime) {
        const ack =
          (new Date(event.ackTime).getTime() -
            new Date(event.startTime).getTime()) /
          60000;
        bucket.ackSum += ack;
        bucket.ackCount += 1;
      }
      if (event.resolvedTime) {
        const resolve =
          (new Date(event.resolvedTime).getTime() -
            new Date(event.startTime).getTime()) /
          60000;
        bucket.resolveSum += resolve;
        bucket.resolveCount += 1;
      }
    });
    return {
      ackSeries: days.map((day) =>
        day.ackCount ? Math.round(day.ackSum / day.ackCount) : 0
      ),
      resolveSeries: days.map((day) =>
        day.resolveCount ? Math.round(day.resolveSum / day.resolveCount) : 0
      ),
    };
  }, [housekeepingEvents]);

  const housekeepingTrend = useMemo(
    () => buildTrend(housekeepingEvents),
    [housekeepingEvents]
  );

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Housekeeping SLA
        </p>
        <h1 className="text-3xl font-semibold text-slate-100">
          Cleaning operations status
        </h1>
        <p className="text-sm text-slate-400">
          Bathroom signals use entry and handwash zones only. No private areas captured.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <KpiCard
          title="Completion rate"
          value={formatPercent(completionRate)}
          subtitle="Floors cleaned in last cycle"
          status={completionRate > 0.9 ? "green" : "amber"}
          icon={<CheckCircle2 className="h-4 w-4" aria-hidden />}
          progress={completionRate}
        />
        <KpiCard
          title="Avg time to acknowledge"
          value={formatDurationMinutes(slaMetrics.avgAckMinutes)}
          subtitle="Response time"
          status="blue"
          icon={<Timer className="h-4 w-4" aria-hidden />}
          sparkline={{ data: slaTrend.ackSeries, color: "#38bdf8" }}
        />
        <KpiCard
          title="Avg time to resolve"
          value={formatDurationMinutes(slaMetrics.avgResolveMinutes)}
          subtitle="Completion SLA"
          status="green"
          icon={<Sparkles className="h-4 w-4" aria-hidden />}
          sparkline={{ data: slaTrend.resolveSeries, color: "#10b981" }}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard
          title="Service-needed by type"
          subtitle="Active housekeeping signals"
          footer={
            <div className="flex flex-wrap gap-2 text-xs text-slate-400">
              {serviceTypeCounts.map((entry) => (
                <span key={entry.name} className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
                  {entry.name} ({entry.value})
                </span>
              ))}
            </div>
          }
        >
          <DonutChart data={serviceTypeCounts} />
        </ChartCard>

        <ChartCard title="Housekeeping trend" subtitle="7-day event volume" className="lg:col-span-2">
          <LineTrendChart
            data={housekeepingTrend.map((entry) => ({ name: entry.day, count: entry.count }))}
            lines={[{ key: "count", color: "#10b981", label: "Events" }]}
          />
        </ChartCard>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/90 p-5 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.45)]">
          <SectionHeader
            title="Cleaning completion by zone"
            subtitle="Latest verification pass"
          />
          <div className="mt-4 space-y-4">
            {Object.entries(completionByFloor).map(([floor, zones]) => (
              <div key={floor}>
                <p className="text-xs font-semibold uppercase text-slate-400">{floor}</p>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {zones.map((zone) => (
                    <div
                      key={`${zone.floor}-${zone.zone}`}
                      className={`flex items-center justify-between rounded-xl border px-3 py-2 text-sm ${
                        zone.completed
                          ? "border-emerald-200 bg-emerald-50/70 text-emerald-900"
                          : "border-amber-200 bg-amber-50/70 text-amber-900"
                      }`}
                    >
                      <div>
                        <p className="font-semibold">{zone.zone}</p>
                        <p className="text-[11px] text-slate-400">
                          {zone.completedAt
                            ? `Completed ${formatDateTime(zone.completedAt)}`
                            : "Pending sweep"}
                        </p>
                      </div>
                      <span className="text-[11px] font-semibold">
                        {zone.completed ? "Done" : "Pending"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/90 p-5 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.45)]">
          <SectionHeader
            title="Service-needed signals"
            subtitle="Restrooms, bins, and litter hotspots"
          />
          <div className="mt-4 space-y-3">
            {serviceNeeded.slice(0, 6).map((event) => (
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
                </div>
              </div>
            ))}
            {!serviceNeeded.length ? (
              <p className="text-sm text-slate-400">No service-needed alerts.</p>
            ) : null}
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/90 p-5 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.45)]">
          <SectionHeader title="Hotspot heatmap" subtitle="Repeat cleaning alerts" />
          <div className="mt-4">
            <HeatmapGrid
              items={hotspots.map((spot) => ({ label: spot.zone, value: spot.count }))}
              accent="#10b981"
              columns={3}
            />
          </div>
        </div>

        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/90 p-5 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.45)]">
          <SectionHeader title="Hotspot zones" subtitle="Top repeat locations" />
          <div className="mt-4 grid gap-3">
            {hotspots.map((spot) => (
              <div
                key={spot.zone}
                className="flex items-center justify-between rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-2)]/70 px-4 py-3"
              >
                <p className="text-sm font-semibold text-slate-200">{spot.zone}</p>
                <p className="text-xs text-slate-400">{spot.count} events</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}







