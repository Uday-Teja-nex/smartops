"use client";

import { useEffect, useState } from "react";
import { Gauge } from "lucide-react";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { fetchSystemMetrics, ServiceMetrics, SystemMetrics } from "@/lib/api";
import { humanize } from "@/lib/utils";

const POLL_MS = 15_000;

/** Bucket bounds from a Prometheus histogram, so values read "≤ x". */
const formatBound = (seconds: number | null | undefined) => {
  if (typeof seconds !== "number") return null;
  if (!Number.isFinite(seconds)) return "over the largest bucket";
  return seconds < 1 ? `≤ ${Math.round(seconds * 1000)} ms` : `≤ ${seconds} s`;
};

const ServiceBlock = ({ title, data, minSamples }: { title: string; data: ServiceMetrics | undefined; minSamples: number }) => {
  if (!data) return null;
  if (data.error) {
    return (
      <div>
        <h4 className="text-xs font-semibold text-slate-300">{title}</h4>
        <p className="mt-1 text-xs text-rose-300">{data.error}</p>
      </div>
    );
  }
  const p50 = formatBound(data.p50Seconds);
  const p95 = formatBound(data.p95Seconds);
  return (
    <div>
      <h4 className="text-xs font-semibold text-slate-300">{title}</h4>
      {p50 === null ? (
        <p className="mt-1 text-xs text-slate-500">Not enough requests yet (needs {minSamples}).</p>
      ) : (
        <dl className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-300">
          <div><dt className="text-slate-500">Median</dt><dd>{p50}</dd></div>
          <div><dt className="text-slate-500">95th percentile</dt><dd>{p95}</dd></div>
        </dl>
      )}
      {data.outcomes && (
        <p className="mt-2 text-[11px] text-slate-400">
          {Object.entries(data.outcomes).map(([key, share]) => `${humanize(key)} ${share}%`).join(" · ")}
        </p>
      )}
    </div>
  );
};

export const ServiceMetricsPanel = ({ enabled }: { enabled: boolean }) => {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    const load = () => fetchSystemMetrics()
      .then((next) => { if (active) { setMetrics(next); setFailed(false); } })
      .catch(() => { if (active) setFailed(true); });  // keep the last numbers on a failed poll
    void load();
    const timer = window.setInterval(load, POLL_MS);
    return () => { active = false; window.clearInterval(timer); };
  }, [enabled]);

  return (
    <GlassPanel>
      <div className="space-y-4">
        {!metrics && !failed && <p className="text-xs text-slate-500">Loading model metrics…</p>}
        {!metrics && failed && <p className="text-xs text-rose-300">Model metrics are unavailable right now.</p>}
        {metrics && (
          <>
            <ServiceBlock title="Object detection (per frame)" data={metrics.detector} minSamples={metrics.minSamples} />
            <ServiceBlock title="AI review (per incident, including queue wait)" data={metrics.ai} minSamples={metrics.minSamples} />
            <p className="text-[11px] text-slate-600">
              From each service&apos;s Prometheus /metrics: {metrics.scope}.{failed && " Last refresh failed; showing the previous values."}
            </p>
          </>
        )}
      </div>
    </GlassPanel>
  );
};

export const ServiceMetricsHeading = () => (
  <h3 className="mb-3 mt-6 flex items-center gap-2 text-sm font-semibold text-slate-300">
    <Gauge className="h-4 w-4 text-[color:var(--accent)]" />
    Model performance
  </h3>
);
