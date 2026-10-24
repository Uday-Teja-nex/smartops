"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useSmartOps } from "@/app/providers";
import { KpiCard } from "@/components/KpiCard";
import { SectionHeader } from "@/components/SectionHeader";
import { StatusPill } from "@/components/StatusPill";
import { EmptyState } from "@/components/ui/EmptyState";
import { filterEventsByRange, getHotspots, TIME_RANGE_LABELS } from "@/lib/analytics";
import { formatDateTime } from "@/lib/utils";

export default function OverviewPage() {
  const { events, selectedBuildingId, timeRange } = useSmartOps();
  const selected = useMemo(() => filterEventsByRange(
    events.filter((event) => event.buildingId === selectedBuildingId), timeRange),
  [events, selectedBuildingId, timeRange]);
  const open = selected.filter((event) => !["resolved", "false_positive"].includes(event.status));
  const high = open.filter((event) => ["high", "critical"].includes(event.severity));
  const resolved = selected.filter((event) => event.status === "resolved");
  const falsePositives = selected.filter((event) => event.status === "false_positive");
  const hotspots = getHotspots(selected, 5);

  return <div className="space-y-6">
    <SectionHeader title="Building operations" subtitle="Stored incidents for the selected building and time range. Tracking is anonymous; no face or identity recognition." />
    {!selected.length ? <EmptyState title="No incidents in this period" description="New incidents will appear here when the pipeline produces them. Try a different time range or check source health in Monitoring." /> : <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard title="Open incidents" value={String(open.length)} status={high.length ? "amber" : "blue"} helper="Includes incidents awaiting human review" href="/live-ops" />
        <KpiCard title="High priority open" value={String(high.length)} status={high.length ? "red" : "blue"} helper="High or critical severity" href="/live-ops" />
        <KpiCard title="Resolved" value={String(resolved.length)} status="blue" helper="Resolved by an operator" href="/live-ops?status=resolved" />
        <KpiCard title="False positives" value={String(falsePositives.length)} status="blue" helper="Marked by an operator" href="/live-ops?status=false_positive" />
      </div>
      <section className="glass-panel p-5">
        <SectionHeader title="Summary" subtitle={`Computed from ${selected.length} stored incidents · ${TIME_RANGE_LABELS[timeRange]}`} />
        <p className="mt-3 text-sm text-slate-300">{open.length} incidents remain open, including {high.length} at high or critical severity. {resolved.length} have been resolved and {falsePositives.length} marked as false positives.</p>
      </section>
      <div className="grid gap-6 lg:grid-cols-3">
        <section className="space-y-3 lg:col-span-2">
          <SectionHeader title="Recent incidents" subtitle="Most recent recorded observations" />
          {[...selected].sort((a, b) => Date.parse(b.startTime) - Date.parse(a.startTime)).slice(0, 8).map((event) => <Link
            key={event.id} href={`/incidents/${event.id}`} className="glass-panel flex items-start justify-between gap-3 p-4">
            <div><p className="text-sm font-semibold text-slate-100">{event.shortSummary || event.type.replaceAll("_", " ")}</p>
              <p className="mt-1 text-xs text-slate-400">{event.zone} · {formatDateTime(event.startTime)}</p>
              <p className="mt-1 text-xs text-slate-500">{event.modelProvider === "rule-engine" ? "Rule engine" : event.modelVersion || "Model metadata unavailable"}</p></div>
            <StatusPill status={event.status} />
          </Link>)}
        </section>
        <section className="glass-panel p-5">
          <SectionHeader title="Incidents by zone" subtitle="Counts in the selected period" />
          <div className="mt-4 space-y-3">{hotspots.map((spot) => <div key={spot.zone} className="flex justify-between gap-3 text-sm text-slate-300"><span>{spot.zone}</span><span>{spot.count}</span></div>)}</div>
        </section>
      </div>
    </>}
  </div>;
}
