"use client";

import { useEffect, useState } from "react";
import { Bot, Ruler } from "lucide-react";
import { EventRecord } from "@/lib/types";
import { humanize } from "@/lib/utils";

type Verdict = "consistent" | "doubtful" | "unclear";

const VERDICT_STYLE: Record<Verdict, { label: string; className: string }> = {
  consistent: { label: "Image consistent with rule", className: "bg-emerald-500/15 text-emerald-300" },
  doubtful: { label: "Image casts doubt", className: "bg-amber-500/15 text-amber-300" },
  unclear: { label: "Image unclear", className: "bg-slate-500/20 text-slate-300" },
};

/** How long after creation a missing review is still shown as "in progress". */
const PENDING_WINDOW_MS = 90_000;

export type ReviewState =
  | { kind: "reviewed"; model: string; latencyMs: number | null; verdict: Verdict; scene: string | null;
      observations: string[]; actions: string[]; limitations: string[] }
  | { kind: "unavailable"; reason: string }
  | { kind: "skipped"; reason: string }
  | { kind: "pending" }
  | { kind: "queued" }
  | { kind: "none" };

export const reviewStateOf = (event: EventRecord, now: number): ReviewState => {
  const notes = event.reviewNotes ?? [];
  const unavailable = notes.find((note) => note.startsWith("AI review unavailable"));
  const reviewedIndex = notes.findIndex((note) => note.startsWith("AI review by "));
  const summary = (event.detectionSummary?.aiReview ?? null) as
    | { model?: string; verdict?: string; latencyMs?: number } | null;
  if (reviewedIndex >= 0 && summary?.verdict && summary.verdict in VERDICT_STYLE) {
    const [scene, ...observations] = event.detailedNarrative;
    return {
      kind: "reviewed",
      model: summary.model ?? "unknown model",
      latencyMs: typeof summary.latencyMs === "number" ? summary.latencyMs : null,
      verdict: summary.verdict as Verdict,
      scene: scene ?? null,
      observations,
      actions: event.recommendedActions,
      limitations: notes.slice(reviewedIndex + 1),
    };
  }
  if (unavailable) {
    return { kind: "unavailable", reason: unavailable.replace(/^AI review unavailable:\s*/, "").replace(/\.$/, "") };
  }
  const skipped = notes.find((note) => note.startsWith("AI review skipped"));
  if (skipped) return { kind: "skipped", reason: skipped.replace(/^AI review skipped:\s*/, "").replace(/\.$/, "") };
  if (notes.some((note) => note.startsWith("AI review queued"))) return { kind: "queued" };
  const created = Date.parse(event.startTime);
  if (event.modelProvider === "rule-engine" && Number.isFinite(created) && now - created < PENDING_WINDOW_MS) {
    return { kind: "pending" };
  }
  return { kind: "none" };
};

export const AiReview = ({ event }: { event: EventRecord }) => {
  const [now, setNow] = useState(() => Date.now());
  const state = reviewStateOf(event, now);
  useEffect(() => {
    if (state.kind !== "pending") return;
    const timer = window.setInterval(() => setNow(Date.now()), 5000);
    return () => window.clearInterval(timer);
  }, [state.kind]);

  const ruleMeasured = event.modelProvider === "rule-engine";
  return (
    <div className="space-y-5">
      <section>
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
          <Ruler className="h-4 w-4 text-[color:var(--accent)]" /> {ruleMeasured ? "Measured by rule" : "Detection"}
        </h3>
        <p className="mt-2 text-sm text-slate-200">{event.shortSummary}</p>
        <p className="mt-1 text-[11px] text-slate-500">
          {ruleMeasured
            ? `Deterministic zone rule (${humanize(event.type)}) over tracked YOLO detections · ${event.modelVersion ?? "rules"}`
            : `Source: ${event.modelProvider ?? "unknown"} ${event.modelVersion ?? ""}`}
        </p>
      </section>

      <section>
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
          <Bot className="h-4 w-4 text-[color:var(--accent)]" /> AI review
          <span className="text-[11px] font-normal text-slate-500">advisory · never changes the rule decision</span>
        </h3>
        {state.kind === "reviewed" && (
          <div className="mt-2 space-y-3">
            <p className="flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
              <span className={`rounded-full px-2 py-0.5 font-semibold ${VERDICT_STYLE[state.verdict].className}`}>
                {VERDICT_STYLE[state.verdict].label}
              </span>
              <span className="font-mono">{state.model}</span>
              {state.latencyMs !== null && <span>· {(state.latencyMs / 1000).toFixed(1)} s</span>}
            </p>
            {state.scene && <p className="text-sm text-slate-200">{state.scene}</p>}
            {state.observations.length > 0 && (
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-300">
                {state.observations.map((item) => <li key={item}>{item}</li>)}
              </ul>
            )}
            {state.actions.length > 0 && (
              <>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Suggested checks</h4>
                <ul className="list-disc space-y-1 pl-5 text-sm text-slate-300">
                  {state.actions.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </>
            )}
            {state.limitations.length > 0 && (
              <p className="text-[11px] text-slate-500">Limits: {state.limitations.join(" ")}</p>
            )}
          </div>
        )}
        {state.kind === "unavailable" && (
          <p role="status" className="mt-2 rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
            AI review unavailable: {state.reason}. The rule result above stands on its own.
          </p>
        )}
        {state.kind === "skipped" && (
          <p role="status" className="mt-2 text-sm text-slate-400">
            AI review skipped: {state.reason}. The rule result above stands on its own.
          </p>
        )}
        {state.kind === "queued" && (
          <p role="status" className="mt-2 text-sm text-slate-400">
            AI review queued. It runs after the evidence clip is saved; the rule result above is already final.
          </p>
        )}
        {state.kind === "pending" && (
          <p role="status" className="mt-2 text-sm text-slate-400">AI review in progress…</p>
        )}
        {state.kind === "none" && (
          <p className="mt-2 text-sm text-slate-500">No AI review was recorded for this incident.</p>
        )}
      </section>
    </div>
  );
};

/** Notes that are not part of the AI review (evidence problems, pipeline notices). */
export const otherNotes = (event: EventRecord) => {
  const notes = event.reviewNotes ?? [];
  const reviewed = notes.findIndex((note) => note.startsWith("AI review by "));
  return notes.filter((note, index) => !note.startsWith("AI review") && (reviewed < 0 || index < reviewed));
};
