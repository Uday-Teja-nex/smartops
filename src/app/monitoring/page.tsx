"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  AlertOctagon,
  Camera,
  Layers,
  RefreshCw,
  Server,
} from "lucide-react";
import { useSmartOps } from "@/app/providers";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { SkeletonPanel } from "@/components/ui/Skeleton";
import { SectionHeader } from "@/components/SectionHeader";
import { fetchPipelineStatus } from "@/lib/api";
import { PipelineStatus, SourceStatus } from "@/lib/types";
import { SOURCE_STATUS_COLORS, hexToRgba } from "@/lib/visuals";
import { classNames, formatDateTime } from "@/lib/utils";

const STATE_STYLES: Record<string, string> = {
  queued: "bg-sky-400/10 text-sky-300",
  processing: "bg-amber-400/10 text-amber-300",
  persisted: "bg-emerald-400/10 text-emerald-300",
  ignored: "bg-slate-400/10 text-slate-400",
  retrying: "bg-orange-400/10 text-orange-300",
  dead: "bg-rose-400/10 text-rose-300",
};

export default function MonitoringPage() {
  const { sources, backendStatus } = useSmartOps();
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const next = await fetchPipelineStatus();
      setStatus(next);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load pipeline status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // State updates in refresh occur after the network request settles.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
    const interval = window.setInterval(() => void refresh(), 10000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Realtime Monitoring"
        subtitle="Live pipeline state: candidate queue, processing outcomes, and per-source health"
        action={
          <Button
            variant="outline"
            size="sm"
            icon={<RefreshCw className="h-3.5 w-3.5" />}
            onClick={() => void refresh()}
          >
            Refresh
          </Button>
        }
      />

      {backendStatus !== "connected" && (
        <GlassPanel className="border-amber-500/25 text-sm text-amber-200">
          Backend is unreachable — pipeline telemetry requires the Docker stack.
        </GlassPanel>
      )}

      {/* Queue stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <GlassPanel>
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-400/10 text-sky-300">
              <Layers className="h-4 w-4" />
            </span>
            <div>
              <p className="text-2xl font-semibold text-slate-100">
                {status?.queued ?? "–"}
              </p>
              <p className="text-xs text-slate-500">Candidates queued</p>
            </div>
          </div>
        </GlassPanel>
        <GlassPanel>
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-rose-400/10 text-rose-300">
              <AlertOctagon className="h-4 w-4" />
            </span>
            <div>
              <p className="text-2xl font-semibold text-slate-100">
                {status?.deadLetter ?? "–"}
              </p>
              <p className="text-xs text-slate-500">Dead-lettered jobs</p>
            </div>
          </div>
        </GlassPanel>
        <GlassPanel>
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-400/10 text-emerald-300">
              <Server className="h-4 w-4" />
            </span>
            <div>
              <p className="truncate font-mono text-sm text-slate-300">
                {status?.queue ?? "–"}
              </p>
              <p className="text-xs text-slate-500">Redis queue</p>
            </div>
          </div>
        </GlassPanel>
      </div>

      <div className="grid gap-6 xl:grid-cols-5">
        {/* Recent candidate activity */}
        <div className="xl:col-span-3">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-300">
            <Activity className="h-4 w-4 text-[color:var(--accent)]" />
            Recent candidate activity
          </h3>
          {loading ? (
            <SkeletonPanel lines={6} />
          ) : error ? (
            <EmptyState
              title="Pipeline telemetry unavailable"
              description={error}
            />
          ) : !status || status.recentStatuses.length === 0 ? (
            <EmptyState
              title="No candidates processed yet"
              description="Once video-ingest discovers enabled sources, candidate windows appear here as they move through detection and review."
            />
          ) : (
            <GlassPanel padded={false} className="divide-y divide-white/5">
              {status.recentStatuses.slice(0, 20).map((candidate) => (
                <motion.div
                  key={`${candidate.candidateId}-${candidate.updatedAt}`}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-3 px-4 py-3"
                >
                  <span
                    className={classNames(
                      "rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide",
                      STATE_STYLES[candidate.state] ?? "bg-white/5 text-slate-400"
                    )}
                  >
                    {candidate.state}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-mono text-xs text-slate-300">
                      {candidate.candidateId}
                    </p>
                    <p className="truncate text-[11px] text-slate-500">
                      {candidate.sourceName ?? candidate.sourceId ?? "unknown source"}
                      {candidate.incidentId ? ` → ${candidate.incidentId}` : ""}
                      {candidate.error ? ` · ${candidate.error}` : ""}
                    </p>
                  </div>
                  {candidate.updatedAt && (
                    <span className="shrink-0 text-[10px] text-slate-600">
                      {formatDateTime(String(candidate.updatedAt))}
                    </span>
                  )}
                </motion.div>
              ))}
            </GlassPanel>
          )}
        </div>

        {/* Source health tiles */}
        <div className="xl:col-span-2">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-300">
            <Camera className="h-4 w-4 text-[color:var(--accent)]" />
            Source health
          </h3>
          {sources.length === 0 ? (
            <EmptyState
              title="No sources registered"
              description="Register a video source to see its adapter health here."
            />
          ) : (
            <div className="space-y-3">
              {sources.map((source) => {
                const color =
                  SOURCE_STATUS_COLORS[source.status as SourceStatus] ?? "#64748b";
                return (
                  <GlassPanel key={source.id} className="!p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-slate-200">
                          {source.name}
                        </p>
                        <p className="text-[11px] text-slate-500">
                          {source.floor} · {source.zone} · {source.sourceType}
                        </p>
                      </div>
                      <span
                        className="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide"
                        style={{ backgroundColor: hexToRgba(color, 0.12), color }}
                      >
                        <span
                          className={classNames(
                            "h-1.5 w-1.5 rounded-full",
                            (source.status === "online" ||
                              source.status === "processing") &&
                              "pulse-dot"
                          )}
                          style={{ backgroundColor: color }}
                        />
                        {source.status}
                      </span>
                    </div>
                    {source.health?.lastError ? (
                      <p className="mt-2 truncate rounded-lg bg-rose-500/10 px-2 py-1 text-[11px] text-rose-300">
                        {String(source.health.lastError)}
                      </p>
                    ) : source.health?.lastSeen ? (
                      <p className="mt-2 text-[11px] text-slate-600">
                        probe ok · seen {formatDateTime(String(source.health.lastSeen))}
                        {typeof source.health.latencyMs === "number" &&
                          ` · ${Math.round(source.health.latencyMs)}ms`}
                      </p>
                    ) : (
                      <p className="mt-2 text-[11px] text-slate-600">no probe yet</p>
                    )}
                  </GlassPanel>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
