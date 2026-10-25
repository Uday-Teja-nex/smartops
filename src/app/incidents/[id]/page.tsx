"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  CheckCircle2,
  ClipboardCheck,
  Clock,
  History,
  MessageSquare,
  ScanEye,
  Send,
  UserCheck,
} from "lucide-react";
import { useAuth } from "@/app/auth";
import { useSmartOps } from "@/app/providers";
import { Badge } from "@/components/Badge";
import { StatusPill } from "@/components/StatusPill";
import {
  detectionsToAnnotations,
  EvidenceVideoPlayer,
} from "@/components/EvidenceVideoPlayer";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState } from "@/components/ui/EmptyState";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { SkeletonPanel } from "@/components/ui/Skeleton";
import {
  addIncidentComment,
  fetchEvidenceUrl,
  fetchIncidentDetail,
  patchIncidentAction,
} from "@/lib/api";
import { IncidentDetail } from "@/lib/types";
import { formatConfidence, formatDateTime, formatDurationMinutes } from "@/lib/utils";
import { getCategoryStyle, getSeverityStyle } from "@/lib/visuals";

const slaCountdown = (slaDueAt: string | null | undefined, status: string) => {
  if (!slaDueAt || ["resolved", "false_positive"].includes(status)) return null;
  const remaining = new Date(slaDueAt).getTime() - Date.now();
  const overdue = remaining < 0;
  const minutes = Math.abs(Math.round(remaining / 60000));
  const label = formatDurationMinutes(minutes);
  return { overdue, label };
};

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const incidentId = params.id;
  const { sources, events } = useSmartOps();
  const liveIncident = events.find((event) => event.id === incidentId);
  const evidenceRevision = JSON.stringify([liveIncident?.evidence, liveIncident?.reviewNotes]);
  const { hasRole, user } = useAuth();
  const canAct = hasRole("operator");

  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [clipUrl, setClipUrl] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const next = await fetchIncidentDetail(incidentId);
      setDetail(next);
      setError(null);

      let resolved: string | null = null;
      const clip = next.evidenceItems.find((item) => item.kind === "clip");
      if (clip) {
        try {
          resolved = (await fetchEvidenceUrl(clip.id)).url;
        } catch {
          resolved = null;
        }
      }
      setClipUrl(resolved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load incident");
    } finally {
      setLoading(false);
    }
  }, [incidentId]);

  useEffect(() => {
    // State updates in load occur after the network request settles.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load, evidenceRevision]);

  const annotations = useMemo(() => {
    if (!detail) return [];
    const clip = detail.evidenceItems.find((item) => item.kind === "clip");
    const windowStart = Number(clip?.meta?.windowStart ?? 0);
    return detectionsToAnnotations(detail.detections, windowStart);
  }, [detail]);

  const runAction = async (
    action: "acknowledge" | "assign" | "resolve" | "false-positive"
  ) => {
    setBusy(true);
    try {
      await patchIncidentAction(incidentId, action, user?.name);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  };

  const submitComment = async () => {
    if (!comment.trim()) return;
    setBusy(true);
    try {
      await addIncidentComment(incidentId, comment.trim());
      setComment("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comment failed");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <SkeletonPanel lines={2} />
        <div className="grid gap-4 xl:grid-cols-2">
          <SkeletonPanel lines={8} />
          <SkeletonPanel lines={8} />
        </div>
      </div>
    );
  }

  if (error && !detail) {
    return (
      <ErrorState
        title="Incident unavailable"
        description={error}
        action={
          <Link href="/live-ops">
            <Button variant="outline" size="sm" icon={<ArrowLeft className="h-3.5 w-3.5" />}>
              Back to Live Ops
            </Button>
          </Link>
        }
      />
    );
  }

  if (!detail) return null;

  const sla = slaCountdown(detail.slaDueAt, detail.status);
  const source = sources.find((item) => item.id === detail.sourceId);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Link
            href="/live-ops"
            className="mb-2 inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Live Ops
          </Link>
          <h1 className="text-2xl font-semibold text-slate-100">
            {detail.shortSummary}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            {detail.zone} · {detail.floor} · {formatDateTime(detail.startTime)} ·{" "}
            <span className="font-mono text-xs">{detail.id}</span>
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Badge
              label={detail.category}
              className="!normal-case"
              style={getCategoryStyle(detail.category)}
            />
            {detail.subcategory && (
              <Badge label={detail.subcategory.replaceAll("_", " ")} className="!normal-case" tone="slate" />
            )}
            <Badge
              label={`Severity: ${detail.severity}`}
              className="!normal-case"
              style={getSeverityStyle(detail.severity)}
            />
            <StatusPill status={detail.status} />
            {sla && (
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
                  sla.overdue
                    ? "bg-rose-500/15 text-rose-300"
                    : "bg-white/5 text-slate-300"
                }`}
              >
                <Clock className="h-3 w-3" />
                {sla.overdue ? `SLA overdue by ${sla.label}` : `SLA due in ${sla.label}`}
              </span>
            )}
          </div>
        </div>

        {canAct && (
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              icon={<ClipboardCheck className="h-3.5 w-3.5" />}
              onClick={() => void runAction("acknowledge")}
            >
              Acknowledge
            </Button>
            <Button
              size="sm"
              variant="primary"
              disabled={busy}
              icon={<UserCheck className="h-3.5 w-3.5" />}
              onClick={() => void runAction("assign")}
            >
              Assign to me
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              icon={<CheckCircle2 className="h-3.5 w-3.5" />}
              onClick={() => void runAction("resolve")}
            >
              Resolve
            </Button>
            <Button
              size="sm"
              variant="danger"
              disabled={busy}
              icon={<AlertTriangle className="h-3.5 w-3.5" />}
              onClick={() => void runAction("false-positive")}
            >
              False positive
            </Button>
          </div>
        )}
      </div>

      {error && (
        <GlassPanel className="border-rose-500/25 text-sm text-rose-200">{error}</GlassPanel>
      )}

      <div className="grid gap-6 xl:grid-cols-5">
        {/* Left: evidence + narrative */}
        <div className="space-y-6 xl:col-span-3">
          <GlassPanel>
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
              <ScanEye className="h-4 w-4 text-[color:var(--accent)]" />
              Evidence
              <span className="ml-auto text-[10px] uppercase tracking-wide text-slate-600">
                {annotations.length > 0
                  ? `${detail.detections.length} detections overlayed`
                  : "no detection overlay available"}
              </span>
            </h3>
            {clipUrl ? (
              <EvidenceVideoPlayer
                src={clipUrl}
                sourceLabel={source?.sourceUri}
                annotations={annotations}
              />
            ) : (
              <div className="mt-3 rounded-xl border border-dashed border-[color:var(--glass-border)] p-8 text-center text-xs text-slate-500">
                No playable evidence clip is available for this incident.
              </div>
            )}
            <p className="mt-3 text-[11px] text-slate-600">
              Bounding boxes come from persisted YOLO detections; nothing is
              simulated. Evidence access is restricted and audited.
            </p>
          </GlassPanel>

          <GlassPanel>
            <h3 className="text-sm font-semibold text-slate-300">What happened</h3>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-300">
              {detail.detailedNarrative.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <h3 className="mt-6 text-sm font-semibold text-slate-300">
              Recommended actions
            </h3>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-300">
              {detail.recommendedActions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            {detail.reviewNotes && detail.reviewNotes.length > 0 && (
              <>
                <h3 className="mt-6 text-sm font-semibold text-amber-300/90">
                  Review notes
                </h3>
                <ul className="mt-3 list-disc space-y-2 pl-5 text-xs text-amber-200/70">
                  {detail.reviewNotes.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </>
            )}
          </GlassPanel>

          <GlassPanel>
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
              <Bot className="h-4 w-4 text-[color:var(--accent)]" /> Model & detection metadata
            </h3>
            <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-[11px] uppercase tracking-wide text-slate-600">Provider</dt>
                <dd className="mt-0.5 font-mono text-xs text-slate-300">
                  {detail.modelProvider ?? "unknown"}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wide text-slate-600">Model</dt>
                <dd className="mt-0.5 font-mono text-xs text-slate-300">
                  {detail.modelVersion ?? "unknown"}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wide text-slate-600">Confidence</dt>
                <dd className="mt-0.5 font-mono text-xs text-slate-300">
                  {formatConfidence(detail.confidence)}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wide text-slate-600">Candidate</dt>
                <dd className="mt-0.5 truncate font-mono text-xs text-slate-300">
                  {detail.candidateId ?? "—"}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wide text-slate-600">Detections</dt>
                <dd className="mt-0.5 font-mono text-xs text-slate-300">
                  {detail.detections.length}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wide text-slate-600">Detector</dt>
                <dd className="mt-0.5 font-mono text-xs text-slate-300">
                  {String(detail.detectionSummary?.modelName ?? detail.detectionSummary?.detectorStatus ?? "—")}
                </dd>
              </div>
            </dl>
          </GlassPanel>
        </div>

        {/* Right: timeline + comments */}
        <div className="space-y-6 xl:col-span-2">
          <GlassPanel>
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
              <History className="h-4 w-4 text-[color:var(--accent)]" /> Timeline
            </h3>
            {detail.events.length === 0 ? (
              <p className="mt-3 text-xs text-slate-600">No audit events recorded.</p>
            ) : (
              <ol className="mt-4 space-y-0">
                {detail.events.map((event, index) => (
                  <li key={event.id} className="relative flex gap-3 pb-5 last:pb-0">
                    {index < detail.events.length - 1 && (
                      <span className="absolute left-[5px] top-4 h-full w-px bg-white/10" />
                    )}
                    <span className="relative mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full border border-[color:var(--accent)]/60 bg-[color:var(--bg)]" />
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-slate-300">
                        {event.action.replace(/_/g, " ")}
                        {event.toStatus && (
                          <span className="text-slate-500"> → {event.toStatus}</span>
                        )}
                      </p>
                      <p className="text-[11px] text-slate-500">
                        {event.actor} · {formatDateTime(event.createdAt)}
                      </p>
                      {event.note && (
                        <p className="mt-1 rounded-lg bg-white/4 px-2 py-1 text-[11px] text-slate-400">
                          {event.note}
                        </p>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </GlassPanel>

          <GlassPanel>
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
              <MessageSquare className="h-4 w-4 text-[color:var(--accent)]" /> Comments
            </h3>
            <div className="mt-4 space-y-3">
              {detail.comments.length === 0 && (
                <p className="text-xs text-slate-600">No comments yet.</p>
              )}
              {detail.comments.map((item) => (
                <div key={item.id} className="rounded-xl bg-white/4 px-3 py-2.5">
                  <p className="text-xs text-slate-300">{item.body}</p>
                  <p className="mt-1 text-[10px] text-slate-600">
                    {item.author} · {formatDateTime(item.createdAt)}
                  </p>
                </div>
              ))}
            </div>
            {canAct && (
              <div className="mt-4 flex gap-2">
                <input
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void submitComment();
                  }}
                  placeholder="Add an operational note…"
                  className="min-w-0 flex-1 rounded-xl border border-[color:var(--glass-border)] bg-white/5 px-3 py-2 text-xs text-slate-200 focus:outline-none"
                />
                <Button
                  size="sm"
                  variant="primary"
                  disabled={busy || !comment.trim()}
                  icon={<Send className="h-3.5 w-3.5" />}
                  onClick={() => void submitComment()}
                >
                  Post
                </Button>
              </div>
            )}
          </GlassPanel>

          <GlassPanel>
            <h3 className="text-sm font-semibold text-slate-300">Source</h3>
            {source ? (
              <div className="mt-3 space-y-1 text-xs text-slate-400">
                <p className="font-semibold text-slate-200">{source.name}</p>
                <p>
                  {source.floor} · {source.zone} · {source.sourceType}
                </p>
                <p className="truncate font-mono text-[10px] text-slate-600">
                  {source.sourceUri}
                </p>
                <Link
                  href="/sources"
                  className="inline-block pt-1 text-[11px] font-semibold text-[color:var(--accent)] hover:underline"
                >
                  Manage sources →
                </Link>
              </div>
            ) : (
              <p className="mt-3 text-xs text-slate-600">
                Source {detail.sourceId} is no longer registered.
              </p>
            )}
          </GlassPanel>
        </div>
      </div>

      {detail.detections.length === 0 && (
        <EmptyState
          icon={<ScanEye className="h-5 w-5" />}
          title="No persisted detections for this incident"
          description="This incident was created without a detector pass (for example a rule-based source-health incident, or the detector was disabled). The evidence player shows footage without overlays rather than fabricating boxes."
        />
      )}
    </div>
  );
}
