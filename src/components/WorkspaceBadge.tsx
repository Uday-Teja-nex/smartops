"use client";

import { useEffect, useState } from "react";
import { fetchOrg, OrgInfo } from "@/lib/api";

const hexToRgb = (hex: string) => {
  const value = Number.parseInt(hex.slice(1), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
};

/** Shows the signed-in workspace and applies its accent colour to the theme. */
export const WorkspaceBadge = ({ enabled }: { enabled: boolean }) => {
  const [org, setOrg] = useState<OrgInfo | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    fetchOrg().then((next) => { if (active) setOrg(next); }).catch(() => { /* header shows nothing */ });
    return () => { active = false; };
  }, [enabled]);

  const accent = typeof org?.settings?.accent === "string" && /^#[0-9a-fA-F]{6}$/.test(org.settings.accent)
    ? org.settings.accent : null;

  useEffect(() => {
    if (!accent) return;
    const root = document.documentElement;
    const [r, g, b] = hexToRgb(accent);
    root.style.setProperty("--accent", accent);
    root.style.setProperty("--accent-strong", accent);
    root.style.setProperty("--accent-soft", `rgba(${r}, ${g}, ${b}, 0.12)`);
    return () => {
      for (const name of ["--accent", "--accent-strong", "--accent-soft"]) root.style.removeProperty(name);
    };
  }, [accent]);

  if (!org) return null;
  return (
    <span className="inline-flex max-w-[16rem] items-center gap-2 truncate rounded-lg border border-[color:var(--glass-border)] px-2.5 py-1 text-xs font-semibold text-slate-200"
      title={`Workspace: ${org.name}`}>
      <span aria-hidden className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: accent ?? "var(--accent)" }} />
      <span className="truncate">{org.name}</span>
    </span>
  );
};
