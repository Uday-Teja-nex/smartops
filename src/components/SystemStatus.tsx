"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { fetchSystemStatus, SystemStatus } from "@/lib/api";

const POLL_MS = 10_000;

/** Polls /v1/system/status; null until the first answer, "error" if the API itself fails. */
export const useSystemStatus = (enabled = true) => {
  const [status, setStatus] = useState<SystemStatus | "error" | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const next = await fetchSystemStatus();
        if (active) setStatus(next);
      } catch {
        // One failed poll (slow while a service is down) must not hide a
        // degraded state that is still true: keep the last known status.
        if (active) setStatus((previous) => (previous && previous !== "error" ? previous : "error"));
      }
      if (active) timer = setTimeout(() => void poll(), POLL_MS);
    };
    void poll();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [enabled]);
  return status;
};

/** App-wide strip naming each failed component and what it means right now. */
export const DegradedBanner = () => {
  const status = useSystemStatus();
  if (!status || status === "error" || status.ok) return null;
  const down = status.components.filter((component) => !component.ok);
  return (
    <div role="status" aria-live="polite" className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100">
      <p className="flex items-center gap-2 font-semibold">
        <AlertTriangle className="h-4 w-4" /> Running in a degraded state. SmartOps recovers automatically when service returns.
      </p>
      <ul className="mt-1 space-y-0.5 pl-6 text-xs text-amber-200/90">
        {down.map((component) => (
          <li key={component.id}>
            <span className="font-semibold">{component.label}:</span> {component.impact} <span className="text-amber-200/60">({component.detail})</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

export const ServiceList = ({ status }: { status: SystemStatus | "error" | null }) => {
  if (status === null) return <p className="text-xs text-slate-500">Checking services…</p>;
  if (status === "error") return <p className="text-xs text-rose-300">The API is unreachable, so other services cannot be checked.</p>;
  return (
    <ul className="divide-y divide-white/5">
      {status.components.map((component) => (
        <li key={component.id} className="flex items-start gap-3 py-2">
          {component.ok
            ? <CheckCircle2 aria-label="up" className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
            : <XCircle aria-label="down" className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />}
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-200">{component.label}</p>
            <p className="break-words text-[11px] text-slate-500">{component.detail}</p>
            {component.impact && <p className="text-[11px] text-amber-200">{component.impact}</p>}
          </div>
        </li>
      ))}
    </ul>
  );
};
