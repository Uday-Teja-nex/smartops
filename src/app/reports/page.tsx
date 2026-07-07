"use client";

import { useMemo } from "react";
import { BarChart2, Timer, Target } from "lucide-react";
import { ChartCard } from "@/components/ChartCard";
import { KpiCard } from "@/components/KpiCard";
import { SectionHeader } from "@/components/SectionHeader";
import { LineTrendChart } from "@/components/charts/LineTrendChart";
import { StackedBarChart } from "@/components/charts/StackedBarChart";
import { useSmartOps } from "@/app/providers";
import {
  filterEventsByRange,
  getCountsByCategory,
  getSlaMetrics,
  getHotspots,
} from "@/lib/analytics";
import { formatDurationMinutes, formatPercent, getNowTimestamp } from "@/lib/utils";
import { CATEGORY_COLORS } from "@/lib/visuals";

const BUCKETS = [
  { label: "0-15m", max: 15 },
  { label: "15-30m", max: 30 },
  { label: "30-60m", max: 60 },
  { label: "1-2h", max: 120 },
  { label: "2h+", max: Infinity },
];

export default function ReportsPage() {
  const { events, selectedBuildingId } = useSmartOps();

  const buildingEvents = useMemo(
    () => events.filter((event) => event.buildingId === selectedBuildingId),
    [events, selectedBuildingId]
  );

  const dailyEvents = useMemo(
    () => filterEventsByRange(buildingEvents, "24h"),
    [buildingEvents]
  );
  const weeklyEvents = useMemo(
    () => filterEventsByRange(buildingEvents, "7d"),
    [buildingEvents]
  );

  const dailyCounts = useMemo(
    () => getCountsByCategory(dailyEvents),
    [dailyEvents]
  );
  const weeklyCounts = useMemo(
    () => getCountsByCategory(weeklyEvents),
    [weeklyEvents]
  );
  const weeklySla = useMemo(() => getSlaMetrics(weeklyEvents), [weeklyEvents]);

  const trendByCategory = useMemo(() => {
    const days = new Array(7).fill(0).map((_, index) => ({
      name: `D-${6 - index}`,
      Housekeeping: 0,
      Safety: 0,
      Occupancy: 0,
      Security: 0,
      "Queue & Crowd": 0,
      "System Health": 0,
    }));
    const now = getNowTimestamp();
    weeklyEvents.forEach((event) => {
      const diffDays = Math.floor(
        (now - new Date(event.startTime).getTime()) / (24 * 60 * 60 * 1000)
      );
      if (diffDays >= 0 && diffDays < 7) {
        days[6 - diffDays][event.category] += 1;
      }
    });
    return days;
  }, [weeklyEvents]);

  const slaBuckets = useMemo(() => {
    const ackCounts = BUCKETS.map(() => 0);
    const resolveCounts = BUCKETS.map(() => 0);

    weeklyEvents.forEach((event) => {
      if (event.ackTime) {
        const minutes =
          (new Date(event.ackTime).getTime() -
            new Date(event.startTime).getTime()) /
          60000;
        const bucketIndex = BUCKETS.findIndex((bucket) => minutes <= bucket.max);
        if (bucketIndex >= 0) ackCounts[bucketIndex] += 1;
      }
      if (event.resolvedTime) {
        const minutes =
          (new Date(event.resolvedTime).getTime() -
            new Date(event.startTime).getTime()) /
          60000;
        const bucketIndex = BUCKETS.findIndex((bucket) => minutes <= bucket.max);
        if (bucketIndex >= 0) resolveCounts[bucketIndex] += 1;
      }
    });

    return BUCKETS.map((bucket, index) => ({
      name: bucket.label,
      acknowledge: ackCounts[index],
      resolve: resolveCounts[index],
    }));
  }, [weeklyEvents]);

  const insightCards = useMemo(() => {
    const peakDay = trendByCategory.reduce(
      (max, day) => {
        const total = day.Housekeeping + day.Safety + day.Occupancy;
        if (total > max.total) return { day: day.name, total };
        return max;
      },
      { day: "D-0", total: 0 }
    );

    const topHotspot = getHotspots(weeklyEvents, 1)[0];

    const typeCounts = new Map<string, number>();
    weeklyEvents.forEach((event) => {
      typeCounts.set(event.type, (typeCounts.get(event.type) ?? 0) + 1);
    });
    const topType = Array.from(typeCounts.entries()).sort((a, b) => b[1] - a[1])[0];

    const resolveTimes = weeklyEvents
      .filter((event) => event.resolvedTime)
      .map(
        (event) =>
          (new Date(event.resolvedTime!).getTime() -
            new Date(event.startTime).getTime()) /
          60000
      )
      .sort((a, b) => a - b);
    const medianResolve = resolveTimes.length
      ? resolveTimes[Math.floor(resolveTimes.length / 2)]
      : 0;

    return {
      peakDay,
      topHotspot,
      topType,
      medianResolve,
    };
  }, [trendByCategory, weeklyEvents]);

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Reports
        </p>
        <h1 className="text-3xl font-semibold text-slate-100">
          Weekly operations summary
        </h1>
        <p className="text-sm text-slate-400">
          Generated from the same privacy-safe dataset. No individual tracking.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <KpiCard
          title="Weekly total events"
          value={`${weeklyEvents.length}`}
          subtitle="Last 7 days"
          status="blue"
          icon={<BarChart2 className="h-4 w-4" aria-hidden />}
        />
        <KpiCard
          title="Avg time to acknowledge"
          value={formatDurationMinutes(weeklySla.avgAckMinutes)}
          subtitle="Weekly SLA"
          status="amber"
          icon={<Timer className="h-4 w-4" aria-hidden />}
        />
        <KpiCard
          title="Completion rate"
          value={formatPercent(weeklySla.completionRate)}
          subtitle="Resolved or closed"
          status="green"
          icon={<Target className="h-4 w-4" aria-hidden />}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Events by category"
          subtitle="7-day trend"
          footer={<span className="text-xs text-slate-400">Housekeeping vs Safety vs Occupancy</span>}
        >
          <LineTrendChart
            data={trendByCategory}
            lines={[
              {
                key: "Housekeeping",
                color: CATEGORY_COLORS.Housekeeping,
                label: "Housekeeping",
              },
              { key: "Safety", color: CATEGORY_COLORS.Safety, label: "Safety" },
              {
                key: "Occupancy",
                color: CATEGORY_COLORS.Occupancy,
                label: "Occupancy",
              },
            ]}
          />
        </ChartCard>

        <ChartCard
          title="SLA distribution"
          subtitle="Time to acknowledge vs resolve"
          footer={<span className="text-xs text-slate-400">Counts per bucket</span>}
        >
          <StackedBarChart
            data={slaBuckets}
            series={[
              { key: "acknowledge", label: "Acknowledge", color: "#38bdf8" },
              { key: "resolve", label: "Resolve", color: "#10b981" },
            ]}
          />
        </ChartCard>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/90 p-4 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.45)]">
          <p className="text-xs font-semibold uppercase text-slate-400">Peak day</p>
          <p className="mt-2 text-lg font-semibold text-slate-100">
            {insightCards.peakDay.day}
          </p>
          <p className="text-xs text-slate-400">{insightCards.peakDay.total} events</p>
        </div>
        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/90 p-4 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.45)]">
          <p className="text-xs font-semibold uppercase text-slate-400">Top hotspot</p>
          <p className="mt-2 text-lg font-semibold text-slate-100">
            {insightCards.topHotspot?.zone ?? "-"}
          </p>
          <p className="text-xs text-slate-400">
            {insightCards.topHotspot?.count ?? 0} events
          </p>
        </div>
        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/90 p-4 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.45)]">
          <p className="text-xs font-semibold uppercase text-slate-400">Most common type</p>
          <p className="mt-2 text-lg font-semibold text-slate-100">
            {insightCards.topType?.[0]?.replace(/_/g, " ") ?? "-"}
          </p>
          <p className="text-xs text-slate-400">
            {insightCards.topType?.[1] ?? 0} events
          </p>
        </div>
        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/90 p-4 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.45)]">
          <p className="text-xs font-semibold uppercase text-slate-400">Median resolve</p>
          <p className="mt-2 text-lg font-semibold text-slate-100">
            {formatDurationMinutes(insightCards.medianResolve)}
          </p>
          <p className="text-xs text-slate-400">Median time to resolve</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/90 p-5 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.45)]">
          <SectionHeader title="Daily summary" subtitle="Last 24 hours" />
          <div className="mt-4 space-y-3 text-sm text-slate-200">
            <p>
              Housekeeping events: <strong>{dailyCounts.Housekeeping ?? 0}</strong>
            </p>
            <p>
              Safety & EHS events: <strong>{dailyCounts.Safety ?? 0}</strong>
            </p>
            <p>
              Occupancy events: <strong>{dailyCounts.Occupancy ?? 0}</strong>
            </p>
            <p className="text-xs text-slate-400">
              Summary auto-generated from aggregated analytics only.
            </p>
          </div>
        </div>

        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/90 p-5 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.45)]">
          <SectionHeader title="Weekly narrative" subtitle="Last 7 days" />
          <div className="mt-4 space-y-3 text-sm text-slate-200">
            <p>
              Housekeeping contributed {weeklyCounts.Housekeeping ?? 0} events,
              with elevated activity in pantry and restroom entry zones.
            </p>
            <p>
              Safety signals remained steady at {weeklyCounts.Safety ?? 0} events,
              primarily tied to exit clearance and slip prevention.
            </p>
            <p>
              Occupancy alerts totaled {weeklyCounts.Occupancy ?? 0} events, with
              lobby congestion peaking around shift changes.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}








