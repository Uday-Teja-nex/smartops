"use client";

import { useMemo, useState } from "react";
import { Building2, ShieldAlert, Users } from "lucide-react";
import { useSmartOps } from "@/app/providers";
import { EventDetailDrawer } from "@/components/EventDetailDrawer";
import { EventTable } from "@/components/EventTable";
import { SectionHeader } from "@/components/SectionHeader";
import { DonutChart } from "@/components/charts/DonutChart";
import { ChartCard } from "@/components/ChartCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { filterEventsByRange } from "@/lib/analytics";
import { CATEGORY_COLORS } from "@/lib/visuals";
import { EventRecord } from "@/lib/types";

const CATEGORIES = ["Occupancy", "Security", "Queue & Crowd"] as const;

export default function OccupancySecurityPage() {
  const {
    events,
    sources,
    selectedBuildingId,
    timeRange,
    acknowledgeEvent,
    assignEvent,
    resolveEvent,
    markFalsePositive,
  } = useSmartOps();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const scoped = useMemo(
    () =>
      filterEventsByRange(
        events.filter(
          (event) =>
            event.buildingId === selectedBuildingId &&
            CATEGORIES.includes(event.category as (typeof CATEGORIES)[number])
        ),
        timeRange
      ),
    [events, selectedBuildingId, timeRange]
  );

  const active = scoped.filter((event) =>
    ["active", "acknowledged", "assigned", "in_progress", "escalated", "human_review"].includes(
      event.status
    )
  );

  const byCategory = useMemo(
    () =>
      CATEGORIES.map((category) => ({
        name: category,
        value: scoped.filter((event) => event.category === category).length,
        color: CATEGORY_COLORS[category],
      })).filter((item) => item.value > 0),
    [scoped]
  );

  const hotZones = useMemo(() => {
    const counts = new Map<string, number>();
    for (const event of scoped) {
      counts.set(event.zone, (counts.get(event.zone) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
  }, [scoped]);

  const selectedEvent: EventRecord | null =
    scoped.find((event) => event.id === selectedId) ?? null;
  const camera = selectedEvent
    ? sources.find((item) => item.id === selectedEvent.sourceId) ?? null
    : null;

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Occupancy & Security"
        subtitle="Crowding, queue buildup, occupancy spikes, and security-relevant events"
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <GlassPanel>
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-400/10 text-indigo-300">
              <Users className="h-4 w-4" />
            </span>
            <div>
              <p className="text-2xl font-semibold text-slate-100">
                {scoped.filter((e) => e.category === "Occupancy").length +
                  scoped.filter((e) => e.category === "Queue & Crowd").length}
              </p>
              <p className="text-xs text-slate-500">Occupancy & queue events</p>
            </div>
          </div>
        </GlassPanel>
        <GlassPanel>
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-400/10 text-amber-300">
              <ShieldAlert className="h-4 w-4" />
            </span>
            <div>
              <p className="text-2xl font-semibold text-slate-100">
                {scoped.filter((e) => e.category === "Security").length}
              </p>
              <p className="text-xs text-slate-500">Security events</p>
            </div>
          </div>
        </GlassPanel>
        <GlassPanel>
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[color:var(--accent-soft)] text-[color:var(--accent)]">
              <Building2 className="h-4 w-4" />
            </span>
            <div>
              <p className="text-2xl font-semibold text-slate-100">{active.length}</p>
              <p className="text-xs text-slate-500">Currently open</p>
            </div>
          </div>
        </GlassPanel>
      </div>

      {scoped.length === 0 ? (
        <EmptyState
          icon={<Building2 className="h-5 w-5" />}
          title="No occupancy or security events in this window"
          description="Events appear here when the pipeline classifies crowding, queue buildup, occupancy spikes, restricted-zone entry, or tailgating candidates for this building."
        />
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard title="Events by category" subtitle="Selected time range">
              <DonutChart data={byCategory} />
            </ChartCard>
            <ChartCard title="Hot zones" subtitle="Most affected areas">
              <div className="space-y-2.5 py-2">
                {hotZones.map(([zone, count]) => {
                  const max = hotZones[0]?.[1] ?? 1;
                  return (
                    <div key={zone} className="flex items-center gap-3">
                      <span className="w-36 truncate text-xs text-slate-400">{zone}</span>
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/5">
                        <div
                          className="h-full rounded-full bg-[color:var(--accent-strong)]/70"
                          style={{ width: `${(count / max) * 100}%` }}
                        />
                      </div>
                      <span className="w-6 text-right text-xs font-semibold text-slate-300">
                        {count}
                      </span>
                    </div>
                  );
                })}
              </div>
            </ChartCard>
          </div>

          <EventTable
            events={scoped}
            onSelect={(event) => setSelectedId(event.id)}
            selectedId={selectedId}
          />
        </>
      )}

      <EventDetailDrawer
        event={selectedEvent}
        open={selectedEvent !== null}
        onClose={() => setSelectedId(null)}
        onAcknowledge={() => selectedEvent && acknowledgeEvent(selectedEvent.id)}
        onAssign={() => selectedEvent && assignEvent(selectedEvent.id)}
        onResolve={() => selectedEvent && resolveEvent(selectedEvent.id)}
        onFalsePositive={() => selectedEvent && markFalsePositive(selectedEvent.id)}
        relatedEvents={scoped
          .filter(
            (event) =>
              selectedEvent &&
              event.id !== selectedEvent.id &&
              event.zone === selectedEvent.zone
          )
          .slice(0, 3)}
        camera={camera}
      />
    </div>
  );
}
