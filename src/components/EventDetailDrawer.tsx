"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  Lock,
  ClipboardCheck,
  UserCheck,
  CheckCircle2,
  AlertTriangle,
  ArrowUpRight,
} from "lucide-react";
import { SourceRecord, EventRecord, IncidentDetail } from "@/lib/types";
import {
  fetchEvidenceUrl,
  fetchIncidentDetail,
} from "@/lib/api";
import { formatConfidence, formatDateTime } from "@/lib/utils";
import { Badge } from "@/components/Badge";
import {
  detectionsToAnnotations,
  EvidenceVideoPlayer,
} from "@/components/EvidenceVideoPlayer";
import { StatusPill } from "@/components/StatusPill";
import { getCategoryStyle, getSeverityStyle } from "@/lib/visuals";

export const EventDetailDrawer = ({
  event,
  open,
  onClose,
  onAcknowledge,
  onAssign,
  onResolve,
  onFalsePositive,
  relatedEvents,
  camera,
}: {
  event: EventRecord | null;
  open: boolean;
  onClose: () => void;
  onAcknowledge: () => void;
  onAssign: () => void;
  onResolve: () => void;
  onFalsePositive: () => void;
  relatedEvents: EventRecord[];
  camera: SourceRecord | null;
}) => {
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [clipUrl, setClipUrl] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      closeRef.current?.focus();
    }
  }, [open]);

  const eventId = event?.id;

  // Only show evidence attached to this incident.
  useEffect(() => {
    let active = true;

    const load = async () => {
      if (active) {
        setDetail(null);
        setClipUrl(null);
      }
      if (!open || !eventId) return;
      let resolved: string | null = null;
      try {
        const incidentDetail = await fetchIncidentDetail(eventId);
        if (!active) return;
        setDetail(incidentDetail);
        const clip = incidentDetail.evidenceItems.find(
          (item) => item.kind === "clip"
        );
        if (clip) {
          const presigned = await fetchEvidenceUrl(clip.id);
          if (!active) return;
          resolved = presigned.url;
        }
      } catch {
        // Leave evidence unavailable when the request fails.
      }
      if (active) setClipUrl(resolved);
    };

    void load();
    return () => {
      active = false;
    };
  }, [open, eventId]);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    if (open) {
      window.addEventListener("keydown", handleKey);
    }
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!event) return null;

  const annotations = detail
    ? detectionsToAnnotations(
        detail.detections,
        Number(
          detail.evidenceItems.find((item) => item.kind === "clip")?.meta
            ?.windowStart ?? 0
        )
      )
    : [];

  return (
    <div
      className={`fixed inset-0 z-40 transition ${open ? "visible" : "invisible"}`}
      aria-hidden={!open}
    >
      <div
        className={`absolute inset-0 bg-slate-950/60 backdrop-blur-sm transition ${
          open ? "opacity-100" : "opacity-0"
        }`}
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="event-drawer-title"
        className={`absolute right-0 top-0 h-full w-full max-w-xl overflow-y-auto border-l border-[color:var(--border)] bg-[color:var(--surface)] p-6 shadow-2xl transition ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Event Detail
            </p>
            <h3 id="event-drawer-title" className="text-2xl font-semibold text-slate-100">
              {event.shortSummary}
            </h3>
            <p className="text-sm text-slate-400">
              {event.zone} - {formatDateTime(event.startTime)}
            </p>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded-full border border-[color:var(--border)] px-3 py-1 text-xs font-semibold text-slate-300 hover:bg-slate-800/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
          >
            Close
          </button>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Badge label={event.category} className="!normal-case" style={getCategoryStyle(event.category)} />
          <Badge label={`Severity: ${event.severity}`} className="!normal-case" style={getSeverityStyle(event.severity)} />
          <StatusPill status={event.status} />
        </div>

        <div className="mt-6 grid gap-3 rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-2)]/90 p-4">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="rounded-full bg-slate-800/80 px-3 py-1 text-xs font-semibold text-slate-200">
              Confidence: {formatConfidence(event.confidence)}
            </span>
            <span className="rounded-full bg-slate-800/80 px-3 py-1 text-xs font-semibold text-slate-200">
              Camera: {event.sourceId}
            </span>
          </div>
          <div className="text-sm text-slate-300">
            <p>Building: {event.buildingId}</p>
            <p>Assigned: {event.assignedTo ?? "Unassigned"}</p>
          </div>
        </div>

        <div className="mt-6">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            What happened
          </h4>
          <ul className="mt-2 list-disc space-y-2 pl-5 text-sm text-slate-200">
            {event.detailedNarrative.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>

        <div className="mt-6">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Recommended actions
          </h4>
          <ul className="mt-2 list-disc space-y-2 pl-5 text-sm text-slate-200">
            {event.recommendedActions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>

        <div className="mt-6">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Evidence (restricted)
          </h4>
          {clipUrl ? (
            <EvidenceVideoPlayer
              src={clipUrl}
              sourceLabel={camera?.sourceUri}
              annotations={annotations}
            />
          ) : (
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {[0, 1].map((index) => (
                <div
                  key={`${event.id}-evidence-${index}`}
                  className="relative overflow-hidden rounded-xl border border-[color:var(--border)]"
                >
                  <div className="h-28 w-full bg-gradient-to-br from-slate-800 via-slate-900 to-slate-950" />
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-slate-950/60 text-xs font-semibold uppercase tracking-wide text-white">
                    <Lock className="h-4 w-4" aria-hidden />
                    Restricted
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="mt-2 text-xs text-slate-400">
            Evidence is visible only to authorized staff. No identity or face data is stored.
          </p>
          <Link
            href={`/incidents/${event.id}`}
            className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-[color:var(--accent)] hover:underline"
          >
            Open full incident view <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        {relatedEvents.length ? (
          <div className="mt-6">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Related events
            </h4>
            <div className="mt-3 space-y-3">
              {relatedEvents.map((related) => (
                <div
                  key={related.id}
                  className="rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-2)]/90 px-4 py-3 text-sm"
                >
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-slate-100">
                      {related.shortSummary}
                    </p>
                    <span className="text-xs text-slate-400">
                      {formatDateTime(related.startTime)}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">{related.zone}</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <div className="mt-8 grid gap-3">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onAcknowledge}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-[color:var(--border)] bg-slate-900/70 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
            >
              <ClipboardCheck className="h-4 w-4" aria-hidden />
              Acknowledge
            </button>
            <button
              type="button"
              onClick={onAssign}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
            >
              <UserCheck className="h-4 w-4" aria-hidden />
              Assign
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onResolve}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
            >
              <CheckCircle2 className="h-4 w-4" aria-hidden />
              Resolve
            </button>
            <button
              type="button"
              onClick={onFalsePositive}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-[color:var(--border)] bg-slate-900/70 px-4 py-2 text-sm font-semibold text-slate-300 hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
            >
              <AlertTriangle className="h-4 w-4" aria-hidden />
              Mark false positive
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
};


