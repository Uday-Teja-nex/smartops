"use client";

import Link from "next/link";
import { useMemo } from "react";
import { AIBriefingPanel } from "@/components/AIBriefingPanel";
import { KpiCard } from "@/components/KpiCard";
import { SectionHeader } from "@/components/SectionHeader";
import { StatusPill } from "@/components/StatusPill";
import { useSmartOps } from "@/app/providers";
import {
  filterEventsByRange,
  getActiveEvents,
  getCountsByCategory,
  getCountsBySeverity,
  getHotspots,
  getSlaMetrics,
  scoreStatus,
} from "@/lib/analytics";
import { CLEANING_COMPLETION, OCCUPANCY_NOW, ZONE_CONGESTION } from "@/lib/mockData";
import { formatConfidence, formatDateTime, formatDurationMinutes, formatPercent } from "@/lib/utils";

export default function OverviewPage() {
  const { events, selectedBuildingId, timeRange } = useSmartOps();

  const buildingEvents = useMemo(
    () => events.filter((event) => event.buildingId === selectedBuildingId),
    [events, selectedBuildingId]
  );
  const rangeEvents = useMemo(
    () => filterEventsByRange(buildingEvents, timeRange),
    [buildingEvents, timeRange]
  );
  const activeEvents = useMemo(() => getActiveEvents(rangeEvents), [rangeEvents]);
  const countsByCategory = useMemo(
    () => getCountsByCategory(rangeEvents),
    [rangeEvents]
  );
  const countsBySeverity = useMemo(
    () => getCountsBySeverity(rangeEvents),
    [rangeEvents]
  );
  const highSeverityCount =
    (countsBySeverity.high ?? 0) + (countsBySeverity.critical ?? 0);
  const hotspots = useMemo(() => getHotspots(rangeEvents, 5), [rangeEvents]);
  const slaMetrics = useMemo(() => getSlaMetrics(rangeEvents), [rangeEvents]);

  const cleaningCompletion = useMemo(() => {
    const completed = CLEANING_COMPLETION.filter((entry) => entry.completed).length;
    return completed / CLEANING_COMPLETION.length;
  }, []);

  const totalOccupancy = OCCUPANCY_NOW.reduce(
    (sum, entry) => sum + entry.peopleCount,
    0
  );

  const activeIssues = activeEvents
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 6);

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          SmartOps Overview
        </p>
        <h1 className="text-3xl font-semibold text-slate-100">
          Building health at a glance
        </h1>
        <p className="text-sm text-slate-400">
          Aggregated analytics only. No identity data is collected or displayed.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <KpiCard
          title="Active issues"
          value={`${activeEvents.length}`}
          status={scoreStatus(activeEvents.length, rangeEvents.length)}
          helper="Across all categories"
          href="/live-ops?status=active"
        />
        <KpiCard
          title="Safety signals"
          value={`${countsByCategory.Safety ?? 0}`}
          status={scoreStatus(highSeverityCount, rangeEvents.length)}
          helper="In selected range"
          href="/live-ops?category=Safety"
        />
        <KpiCard
          title="Occupancy now"
          value={`${totalOccupancy}`}
          status={scoreStatus(
            ZONE_CONGESTION.filter((zone) => zone.congestionIndex > 70).length,
            ZONE_CONGESTION.length
          )}
          helper="People count"
          href="/live-ops?category=Occupancy"
        />
        <KpiCard
          title="Cleaning completion"
          value={formatPercent(cleaningCompletion)}
          status={cleaningCompletion > 0.9 ? "green" : "amber"}
          helper="Last 24 hours"
          href="/housekeeping"
        />
      </div>

      <AIBriefingPanel events={rangeEvents} timeRange={timeRange} />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <SectionHeader
            title="Active issues"
            subtitle="Prioritize actions across cleaning, safety, and occupancy"
            action={
              <Link
                href="/live-ops"
                className="rounded-full border border-[color:var(--border)] bg-[color:var(--surface-2)]/90 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-800/70"
              >
                View all alerts
              </Link>
            }
          />
          <div className="grid gap-3">
            {activeIssues.map((event) => (
              <Link
                key={event.id}
                href={`/live-ops?event=${event.id}`}
                className="group rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/95 p-4 shadow-[0_22px_70px_-45px_rgba(2,6,23,0.85)] transition hover:-translate-y-0.5 hover:bg-slate-900/60"
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
                <p className="mt-2 text-xs text-slate-400">
                  Confidence {formatConfidence(event.confidence)}
                </p>
              </Link>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/95 p-5 shadow-[0_22px_70px_-45px_rgba(2,6,23,0.85)]">
            <SectionHeader
              title="Hotspots"
              subtitle="Repeat events by zone"
            />
            <div className="mt-4 space-y-3">
              {hotspots.map((spot) => (
                <div key={spot.zone} className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-slate-200">{spot.zone}</p>
                  <span className="rounded-full bg-slate-800/70 px-3 py-1 text-xs font-semibold text-slate-200">
                    {spot.count} events
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/95 p-5 shadow-[0_22px_70px_-45px_rgba(2,6,23,0.85)]">
            <SectionHeader
              title="SLA pulse"
              subtitle="Average response metrics"
            />
            <div className="mt-4 space-y-3 text-sm text-slate-200">
              <div className="flex items-center justify-between">
                <span>Time to acknowledge</span>
                <span className="font-semibold">
                  {formatDurationMinutes(slaMetrics.avgAckMinutes)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Time to resolve</span>
                <span className="font-semibold">
                  {formatDurationMinutes(slaMetrics.avgResolveMinutes)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Completion rate</span>
                <span className="font-semibold">
                  {formatPercent(slaMetrics.completionRate)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/95 p-5 shadow-[0_22px_70px_-45px_rgba(2,6,23,0.85)]">
          <SectionHeader title="Occupancy by floor" subtitle="Current people count" />
          <div className="mt-4 space-y-3">
            {OCCUPANCY_NOW.map((floor) => {
              const fill = Math.min(
                (floor.peopleCount / floor.capacity) * 100,
                100
              );
              return (
                <div key={floor.floor}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-semibold text-slate-200">{floor.floor}</span>
                    <span className="text-slate-400">
                      {floor.peopleCount}/{floor.capacity}
                    </span>
                  </div>
                  <div className="mt-2 h-2 rounded-full bg-slate-800/70">
                    <div
                      className="h-2 rounded-full bg-emerald-500"
                      style={{ width: `${fill}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/95 p-5 shadow-[0_22px_70px_-45px_rgba(2,6,23,0.85)]">
          <SectionHeader title="Congestion index" subtitle="Lobby and elevator queue" />
          <div className="mt-4 space-y-3">
            {ZONE_CONGESTION.map((zone) => (
              <div key={zone.zone} className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-200">{zone.zone}</p>
                  <p className="text-xs text-slate-400">{zone.floor}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold text-slate-200">
                    {zone.congestionIndex}
                  </span>
                  <span className="rounded-full bg-slate-800/70 px-3 py-1 text-xs font-semibold text-slate-200">
                    {zone.peopleCount} people
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}







