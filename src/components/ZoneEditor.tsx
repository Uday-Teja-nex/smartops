"use client";

import { useState } from "react";
import { useSmartOps } from "@/app/providers";
import { updateSource } from "@/lib/api";
import { DetectionZone, SourceRecord, ZoneRuleConfig } from "@/lib/types";

const ruleNames: Record<string, string> = {
  restricted_entry: "Restricted entry", after_hours_entry: "After-hours entry",
  crowding: "Crowding", queue_build_up: "Queue build-up", loitering: "Loitering",
  unattended_object: "Unattended bag", blocked_exit: "Blocked exit",
};
const newZone = (): DetectionZone => ({ id: "", polygon: [], rules: [{ type: "restricted_entry", durationSeconds: 0 }] });
const inputClass = "w-full rounded-lg border border-slate-600 bg-slate-950 p-2 text-slate-100";
const buttonClass = "rounded-lg border border-slate-600 px-3 py-2 text-sm disabled:opacity-40";

export function ZoneEditor({ source }: { source: SourceRecord }) {
  const { observations, refreshSources, backendStatus } = useSmartOps();
  const observation = observations[source.id];
  const [frame, setFrame] = useState(observation);
  const [zones, setZones] = useState<DetectionZone[]>(() => structuredClone(source.detectionConfig.zones ?? []));
  const [selected, setSelected] = useState<number | null>(null);
  const [draft, setDraft] = useState<DetectionZone>(newZone);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const changeRule = (index: number, patch: Partial<ZoneRuleConfig>) => setDraft((current) => ({
    ...current, rules: current.rules.map((rule, i) => i === index ? { ...rule, ...patch } : rule),
  }));
  const persist = async (next: DetectionZone[]) => {
    setBusy(true); setMessage("");
    try {
      const updated = await updateSource(source.id, { detectionConfig: { ...source.detectionConfig, zones: next } });
      setZones(updated.detectionConfig.zones ?? []);
      await refreshSources();
      setMessage("Saved. The processor will apply these rules automatically.");
      return true;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save zones");
      return false;
    } finally { setBusy(false); }
  };
  const save = async () => {
    if (!draft.id.trim() || draft.polygon.length < 3) { setMessage("Name the zone and draw at least three corners."); return; }
    const zone = { ...draft, id: draft.id.trim() };
    const next = selected === null ? [...zones, zone] : zones.map((old, i) => i === selected ? zone : old);
    if (await persist(next)) setSelected(selected ?? next.length - 1);
  };
  return <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(300px,1fr)]">
    <section className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <button className={buttonClass} disabled={!observation?.previewJpeg || busy} onClick={() => setFrame(observation)}>Freeze latest frame</button>
        <button className={buttonClass} disabled={!draft.polygon.length || busy} onClick={() => setDraft({ ...draft, polygon: draft.polygon.slice(0, -1) })}>Undo corner</button>
        <button className={buttonClass} disabled={busy} onClick={() => setDraft({ ...draft, polygon: [] })}>Redraw polygon</button>
      </div>
      <p className="text-sm text-slate-400">Freeze a frame, then click or tap each corner in order. The last corner connects to the first. Zones use the bottom center of detected objects.</p>
      {frame?.previewJpeg ? <svg viewBox="0 0 1000 1000" preserveAspectRatio="none" role="img" aria-label="Frozen camera frame for drawing a zone"
        style={{ aspectRatio: `${frame.width}/${frame.height}`, touchAction: "none" }} className="w-full cursor-crosshair rounded-xl border border-slate-600"
        onPointerDown={(event) => {
          if (busy || draft.polygon.length >= 64) return;
          const rect = event.currentTarget.getBoundingClientRect();
          const point: [number, number] = [Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height))];
          setDraft((current) => ({ ...current, polygon: [...current.polygon, point] }));
        }}>
        <image href={`data:image/jpeg;base64,${frame.previewJpeg}`} width="1000" height="1000" preserveAspectRatio="none" />
        {zones.filter((_, i) => i !== selected).map((zone) => <polygon key={zone.id} points={zone.polygon.map(([x, y]) => `${x * 1000},${y * 1000}`).join(" ")} fill="#64748b22" stroke="#94a3b8" strokeWidth="3" />)}
        <polygon points={draft.polygon.map(([x, y]) => `${x * 1000},${y * 1000}`).join(" ")} fill="#22d3ee33" stroke="#22d3ee" strokeWidth="4" />
        {draft.polygon.map(([x, y], i) => <circle key={i} cx={x * 1000} cy={y * 1000} r="7" fill="#fde047" />)}
      </svg> : <div className="rounded-xl border border-slate-700 p-10 text-slate-400">Waiting for a real processed frame. Start the source, then freeze its latest frame.</div>}
      {frame && <p className="text-xs text-slate-500">Frozen at {new Date(frame.capturedAt).toLocaleString()} · {draft.polygon.length} corners</p>}
    </section>
    <section className="space-y-4 rounded-xl border border-slate-700 p-4">
      <label className="block text-sm">Saved zone<select className={inputClass} value={selected ?? "new"} disabled={busy} onChange={(event) => {
        const index = event.target.value === "new" ? null : Number(event.target.value);
        setSelected(index); setDraft(index === null ? newZone() : structuredClone(zones[index])); setMessage("");
      }}><option value="new">New zone</option>{zones.map((zone, i) => <option key={i} value={i}>{zone.id}</option>)}</select></label>
      <label className="block text-sm">Zone name<input className={inputClass} maxLength={80} value={draft.id} onChange={(event) => setDraft({ ...draft, id: event.target.value })} /></label>
      {draft.rules.map((rule, index) => <fieldset key={index} className="space-y-3 rounded-lg border border-slate-700 p-3">
        <legend className="px-1 text-xs text-slate-400">Rule {index + 1}</legend>
        <label className="block text-sm">Event<select className={inputClass} value={rule.type} onChange={(event) => changeRule(index, { type: event.target.value })}>{Object.entries(ruleNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="block text-sm">Sustained for (seconds)<input className={inputClass} type="number" min={0} max={86400} step={.5} value={rule.durationSeconds ?? 0} onChange={(event) => changeRule(index, { durationSeconds: Number(event.target.value) })} /></label>
        {["crowding", "queue_build_up"].includes(rule.type) && <label className="block text-sm">Alert when people exceed<input className={inputClass} type="number" min={0} max={10000} value={rule.threshold ?? 0} onChange={(event) => changeRule(index, { threshold: Number(event.target.value) })} /></label>}
        {rule.type === "unattended_object" && <label className="block text-sm">Nearby-person radius (fraction of image)<input className={inputClass} type="number" min={.01} max={1} step={.01} value={rule.radius ?? .15} onChange={(event) => changeRule(index, { radius: Number(event.target.value) })} /></label>}
        {rule.type === "after_hours_entry" && <div className="space-y-2">
          <label className="block text-sm">Schedule timezone<input className={inputClass} value={rule.timezone ?? "UTC"} onChange={(event) => changeRule(index, { timezone: event.target.value })} /></label>
          <p className="text-xs text-slate-400">Entry is allowed during these hours. An empty schedule restricts entry at all times.</p>
          {(rule.allowedHours ?? []).map((window, wi) => <div key={wi} className="space-y-2 border-t border-slate-700 pt-2">
            <div className="flex flex-wrap gap-2">{["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day, di) => <label key={day} className="text-xs"><input type="checkbox" checked={window.days.includes(di)} onChange={(event) => changeRule(index, { allowedHours: rule.allowedHours!.map((w, i) => i === wi ? { ...w, days: event.target.checked ? [...w.days, di] : w.days.filter((d) => d !== di) } : w) })} /> {day}</label>)}</div>
            <div className="flex gap-2">{(["start", "end"] as const).map((key) => <label key={key} className="text-xs">{key === "start" ? "Opens" : "Closes"}<input type="time" className={inputClass} value={window[key]} onChange={(event) => changeRule(index, { allowedHours: rule.allowedHours!.map((w, i) => i === wi ? { ...w, [key]: event.target.value } : w) })} /></label>)}</div>
            <button className={buttonClass} onClick={() => changeRule(index, { allowedHours: rule.allowedHours!.filter((_, i) => i !== wi) })}>Remove hours</button>
          </div>)}
          <button className={buttonClass} onClick={() => changeRule(index, { allowedHours: [...(rule.allowedHours ?? []), { days: [0, 1, 2, 3, 4], start: "09:00", end: "18:00" }] })}>Add allowed hours</button>
        </div>}
        <button className={buttonClass} onClick={() => setDraft({ ...draft, rules: draft.rules.filter((_, i) => i !== index) })}>Remove rule</button>
      </fieldset>)}
      <button className={buttonClass} disabled={draft.rules.length >= 7} onClick={() => setDraft({ ...draft, rules: [...draft.rules, { type: Object.keys(ruleNames).find((type) => !draft.rules.some((r) => r.type === type)) ?? "restricted_entry", durationSeconds: 0 }] })}>Add rule</button>
      <div className="flex gap-2"><button className={buttonClass} disabled={busy || backendStatus !== "connected"} onClick={() => void save()}>{busy ? "Saving…" : "Save zone"}</button>
        {selected !== null && <button className={buttonClass} disabled={busy} onClick={async () => {
          if (await persist(zones.filter((_, i) => i !== selected))) { setSelected(null); setDraft(newZone()); }
        }}>Delete zone</button>}</div>
      {message && <p role="status" className="text-sm text-amber-200">{message}</p>}
    </section>
  </div>;
}
