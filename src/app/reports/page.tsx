"use client";

import { useEffect, useState } from "react";
import { useSmartOps } from "@/app/providers";
import { fetchIncidentReport, IncidentReport } from "@/lib/api";

const minutes = (value: number | null) => value === null ? "No data" : `${value.toFixed(1)} min`;
const percent = (value: number | null) => value === null ? "No data" : `${(value * 100).toFixed(1)}%`;

export default function ReportsPage() {
  const { selectedBuildingId } = useSmartOps();
  const [reports, setReports] = useState<{ building: string; daily: IncidentReport; weekly: IncidentReport } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    async function load() {
      const end = new Date();
      try {
        const [daily, weekly] = await Promise.all([1, 7].map(days => fetchIncidentReport(
          new Date(end.getTime() - days * 86400000).toISOString(), end.toISOString(), selectedBuildingId,
        )));
        if (active) { setReports({ building: selectedBuildingId, daily, weekly }); setError(null); }
      } catch (failure) {
        if (active) setError(failure instanceof Error ? failure.message : "Reports unavailable");
      } finally {
        if (active) setLoading(false);
      }
    }
    if (selectedBuildingId) void load();
    return () => { active = false; };
  }, [selectedBuildingId, revision]);
  const current = reports?.building === selectedBuildingId ? reports : null;
  const refresh = () => { setLoading(true); setError(null); setRevision(value => value + 1); };
  return <div className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h1 className="text-3xl font-semibold text-slate-100">Operations reports</h1>
        <p className="mt-2 text-sm text-slate-400">Computed from all stored incidents in the selected building and period. No AI-generated narrative.</p></div>
      <button onClick={refresh} disabled={loading} className="rounded-lg border border-slate-600 px-4 py-2 text-sm disabled:opacity-50">Refresh</button>
    </div>
    {!selectedBuildingId ? <p>Select a building to view its report.</p>
      : error ? <p role="alert" className="rounded-xl border border-red-500/40 p-5 text-red-300">{error}</p>
      : loading || !current ? <p role="status">Loading stored history…</p>
      : <>
        <p className="text-xs text-slate-400">Snapshot through {new Date(current.weekly.end).toLocaleString()}. Daily buckets use UTC; boundary days may be partial.</p>
        <div className="overflow-x-auto rounded-xl border border-slate-700">
          <table className="w-full text-left text-sm"><thead className="bg-slate-800"><tr><th className="p-3">Computed summary</th><th>Last 24 hours</th><th>Last 7 days</th></tr></thead>
            <tbody>{[
              ["Incidents", current.daily.totalIncidents, current.weekly.totalIncidents],
              ["Average acknowledgement", minutes(current.daily.averageAckMinutes), minutes(current.weekly.averageAckMinutes)],
              ["Average resolution", minutes(current.daily.averageResolveMinutes), minutes(current.weekly.averageResolveMinutes)],
              ["Resolved or marked false positive", percent(current.daily.completionRate), percent(current.weekly.completionRate)],
              ["Marked false positive / all incidents", percent(current.daily.falsePositiveRate), percent(current.weekly.falsePositiveRate)],
            ].map(([label, daily, weekly]) => <tr key={label} className="border-t border-slate-700"><th className="p-3 font-normal">{label}</th><td>{daily}</td><td>{weekly}</td></tr>)}</tbody>
          </table>
        </div>
        <p className="text-xs text-slate-400">Timing averages include only recorded, non-negative durations. Weekly samples: {current.weekly.acknowledgedCount} acknowledgements and {current.weekly.resolvedTimeCount} resolutions. Statuses reflect the current stored state.</p>
        {current.weekly.totalIncidents === 0 ? <p className="rounded-xl border border-slate-700 p-5">No incidents were recorded in this period.</p> : null}
        <div className="grid gap-5 md:grid-cols-2">
          <section className="rounded-xl border border-slate-700 p-4"><h2 className="mb-3 font-semibold">Daily incident counts (UTC)</h2>
            <ul className="space-y-2">{current.weekly.daily.map(day => <li key={day.date} className="flex justify-between"><span>{day.date}</span><span>{day.count}</span></li>)}</ul>
          </section>
          <section className="rounded-xl border border-slate-700 p-4"><h2 className="mb-3 font-semibold">Weekly categories</h2>
            <ul className="space-y-2">{Object.entries(current.weekly.categories).sort((a, b) => b[1] - a[1]).map(([category, count]) => <li key={category} className="flex justify-between"><span>{category}</span><span>{count}</span></li>)}</ul>
          </section>
        </div>
      </>}
  </div>;
}
