"use client";

import { Camera, Server } from "lucide-react";
import { useSmartOps } from "@/app/providers";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { EmptyState } from "@/components/ui/EmptyState";
import { SectionHeader } from "@/components/SectionHeader";
import { ServiceList, useSystemStatus } from "@/components/SystemStatus";
import { ServiceMetricsHeading, ServiceMetricsPanel } from "@/components/ServiceMetricsPanel";
import { SourceStatus } from "@/lib/types";
import { SOURCE_STATUS_COLORS, hexToRgba } from "@/lib/visuals";
import { classNames, formatDateTime, humanize } from "@/lib/utils";

export default function MonitoringPage() {
  const { sources, backendStatus } = useSmartOps();
  const systemStatus = useSystemStatus(backendStatus === "connected");

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Realtime Monitoring"
        subtitle="Which services are up, model latency, and per-camera processing rate, lag, queues and errors"
      />

      {backendStatus !== "connected" && (
        <GlassPanel className="border-amber-500/25 text-sm text-amber-200">
          Backend is unreachable — pipeline telemetry requires the Docker stack.
        </GlassPanel>
      )}

      <div className="grid gap-6 xl:grid-cols-5">
        <div className="xl:col-span-2">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-300">
            <Server className="h-4 w-4 text-[color:var(--accent)]" />
            Services
          </h3>
          <GlassPanel>
            <ServiceList status={systemStatus} />
          </GlassPanel>
          <ServiceMetricsHeading />
          <ServiceMetricsPanel enabled={backendStatus === "connected"} />
        </div>

        {/* Source health tiles */}
        <div className="xl:col-span-3">
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
                        {humanize(source.status)}
                      </span>
                    </div>
                    {typeof source.health?.processingFps === "number" && <dl className="mt-3 grid grid-cols-3 gap-2 text-xs text-slate-300">
                      <div><dt className="text-slate-500">Processed FPS</dt><dd>{source.health.processingFps.toFixed(1)}</dd></div>
                      <div><dt className="text-slate-500">Detector</dt><dd>{typeof source.health.detectorLatencyMs === "number" ? `${Math.round(source.health.detectorLatencyMs)} ms` : "Unavailable"}</dd></div>
                      <div><dt className="text-slate-500">Frame lag</dt><dd>{typeof source.health.processingLagMs === "number" ? `${Math.round(source.health.processingLagMs)} ms` : "Unavailable"}</dd></div>
                      <div><dt className="text-slate-500">Incident queue</dt><dd>{String(source.health.pendingIncidents ?? "Unavailable")}</dd></div>
                      <div><dt className="text-slate-500">Evidence queue</dt><dd>{String(source.health.pendingEvidence ?? "Unavailable")}</dd></div>
                      <div><dt className="text-slate-500">AI review queue</dt><dd>{String(source.health.pendingReviews ?? "Unavailable")}</dd></div>
                      <div><dt className="text-slate-500">Rejected deliveries</dt><dd>{String(source.health.rejectedIncidentVersions ?? "Unavailable")}</dd></div>
                      <div><dt className="text-slate-500">Errors this run</dt><dd>{String(source.health.processingErrors ?? "Unavailable")}</dd></div>
                    </dl>}
                    {typeof source.health?.rejectedIncidentVersions === "number" && source.health.rejectedIncidentVersions > 0 && (
                      <p role="status" className="mt-2 rounded-lg bg-amber-500/10 px-2 py-2 text-xs text-amber-200">
                        {source.health.rejectedIncidentVersions} rejected incident delivery version(s) need attention.
                        They are retained for recovery; later incidents continue processing. Ask an administrator to review the delivery journal.
                      </p>
                    )}
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
