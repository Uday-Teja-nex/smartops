import { generateBriefing, TIME_RANGE_LABELS } from "@/lib/analytics";
import { EventRecord, TimeRange } from "@/lib/types";

export const AIBriefingPanel = ({
  events,
  timeRange,
}: {
  events: EventRecord[];
  timeRange: TimeRange;
}) => {
  const briefing = generateBriefing(events, TIME_RANGE_LABELS[timeRange]);

  return (
    <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/95 p-5 shadow-[0_22px_70px_-45px_rgba(2,6,23,0.85)]">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            AI Briefing
          </p>
          <h3 className="text-lg font-semibold text-slate-100">What matters now</h3>
        </div>
        <span className="rounded-full bg-slate-800/80 px-3 py-1 text-xs font-semibold text-slate-200">
          {TIME_RANGE_LABELS[timeRange]}
        </span>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase text-slate-400">Top signals</p>
          <ul className="list-disc space-y-2 pl-5 text-sm text-slate-200">
            {briefing.highlights.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase text-slate-400">Recommended actions</p>
          <ul className="list-disc space-y-2 pl-5 text-sm text-slate-200">
            {briefing.actions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase text-slate-400">Root cause</p>
          <div className="rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-2)]/90 p-4 text-sm text-slate-200">
            {briefing.rootCause}
          </div>
        </div>
      </div>
    </div>
  );
};


