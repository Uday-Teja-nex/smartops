import { Badge } from "@/components/Badge";
import { EventRecord } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";
import { SEVERITY_COLORS, getCategoryStyle } from "@/lib/visuals";
import { StatusPill } from "@/components/StatusPill";

const severityTextStyles: Record<EventRecord["severity"], string> = {
  low: "text-slate-300",
  medium: "text-amber-200",
  high: "text-orange-200",
  critical: "text-rose-200",
};

export const EventTable = ({
  events,
  onSelect,
  selectedId,
}: {
  events: EventRecord[];
  onSelect: (event: EventRecord) => void;
  selectedId?: string | null;
}) => (
  <div className="overflow-hidden rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/95 shadow-[0_22px_70px_-45px_rgba(2,6,23,0.85)]">
    <div className="grid grid-cols-12 gap-2 border-b border-[color:var(--border)] bg-[color:var(--surface-2)] px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
      <div className="col-span-4">Event</div>
      <div className="col-span-2">Category</div>
      <div className="col-span-2">Severity</div>
      <div className="col-span-2">Location</div>
      <div className="col-span-2">Status</div>
    </div>
    <div className="divide-y divide-[color:var(--border)]">
      {events.map((event) => {
        const isSelected = selectedId === event.id;
        return (
          <button
            key={event.id}
            data-incident-id={event.id}
            type="button"
            onClick={() => onSelect(event)}
            className={`grid w-full grid-cols-12 gap-2 border-l-4 px-4 py-3 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 ${
              isSelected
                ? "bg-emerald-950/40 ring-1 ring-emerald-500/40"
                : "hover:bg-slate-900/40"
            }`}
            style={{ borderLeftColor: SEVERITY_COLORS[event.severity] }}
          >
            <div className="col-span-4">
              <p className="font-semibold text-slate-100">{event.shortSummary}</p>
              <p className="text-xs text-slate-400">
                {formatDateTime(event.startTime)}
              </p>
            </div>
            <div className="col-span-2 text-slate-300">
              <Badge
                label={event.category}
                className="!normal-case"
                style={getCategoryStyle(event.category)}
              />
            </div>
            <div className={`col-span-2 font-semibold ${severityTextStyles[event.severity]}`}>
              {event.severity}
            </div>
            <div className="col-span-2 text-slate-300">{event.zone}</div>
            <div className="col-span-2">
              <StatusPill status={event.status} />
            </div>
          </button>
        );
      })}
    </div>
  </div>
);


