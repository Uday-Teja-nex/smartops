"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import { Copy, Smartphone, X } from "lucide-react";
import { createPhoneCamera, PhoneCameraResult } from "@/lib/api";
import { Building } from "@/lib/types";

const inputClass =
  "mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400";

const CopyField = ({ label, value }: { label: string; value: string }) => {
  const [copied, setCopied] = useState(false);
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <div className="mt-1 flex items-center gap-2">
        <code className="min-w-0 flex-1 break-all rounded-lg bg-black/30 px-3 py-2 text-sm text-emerald-200">{value}</code>
        <button type="button" aria-label={`Copy ${label}`} className="rounded-lg p-2 text-slate-300 hover:bg-white/10"
          onClick={() => {
            void navigator.clipboard?.writeText(value).then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 1500); });
          }}>
          <Copy className="h-4 w-4" />
        </button>
        {copied && <span className="text-[11px] text-emerald-300">Copied</span>}
      </div>
    </div>
  );
};

export const PhoneCameraDialog = ({ buildings, onClose, onCreated }: {
  buildings: Building[];
  onClose: () => void;
  onCreated: () => void;
}) => {
  const [name, setName] = useState("Phone camera");
  const [buildingId, setBuildingId] = useState(buildings[0]?.id ?? "");
  const floors = useMemo(() => buildings.find((b) => b.id === buildingId)?.floors ?? [], [buildings, buildingId]);
  const [floorId, setFloorId] = useState(floors[0]?.id ?? "");
  const zones = floors.find((floor) => floor.id === floorId)?.zones ?? [];
  const [zoneId, setZoneId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PhoneCameraResult | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setResult(await createPhoneCamera({ name: name.trim(), buildingId, floorId: floorId || undefined,
        zoneId: zoneId || undefined }));
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add the phone camera");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="phone-camera-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-lg rounded-2xl border border-[color:var(--glass-border)] bg-[color:var(--surface-1,#0b1220)] p-5 shadow-2xl">
        <div className="flex items-center justify-between">
          <h2 id="phone-camera-title" className="flex items-center gap-2 text-base font-semibold text-slate-100">
            <Smartphone className="h-5 w-5 text-emerald-300" /> Add a phone as a camera
          </h2>
          <button aria-label="Close" onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-white/10"><X className="h-4 w-4" /></button>
        </div>

        {!result ? (
          <form onSubmit={(event) => void submit(event)} className="mt-4 space-y-3">
            <label className="block text-xs text-slate-400">Camera name
              <input required maxLength={120} className={inputClass} value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="block text-xs text-slate-400">Building
              <select className={inputClass} value={buildingId} onChange={(e) => {
                setBuildingId(e.target.value);
                const nextFloors = buildings.find((b) => b.id === e.target.value)?.floors ?? [];
                setFloorId(nextFloors[0]?.id ?? "");
                setZoneId("");
              }}>
                {buildings.map((building) => <option key={building.id} value={building.id}>{building.name}</option>)}
              </select>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-slate-400">Floor
                <select className={inputClass} value={floorId} onChange={(e) => { setFloorId(e.target.value); setZoneId(""); }}>
                  {floors.map((floor) => <option key={floor.id} value={floor.id}>{floor.level} · {floor.name}</option>)}
                </select>
              </label>
              <label className="block text-xs text-slate-400">Area
                <select className={inputClass} value={zoneId} onChange={(e) => setZoneId(e.target.value)}>
                  <option value="">Whole floor</option>
                  {zones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name}</option>)}
                </select>
              </label>
            </div>
            {error && <p role="alert" className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-200">{error}</p>}
            <button type="submit" disabled={busy || !buildingId || !floorId}
              className="w-full rounded-lg bg-emerald-500 px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-40">
              {busy ? "Creating…" : "Create camera and show publish address"}
            </button>
          </form>
        ) : (
          <div className="mt-4 space-y-4 text-sm text-slate-300">
            {!result.publish.lanHostConfigured && (
              <p role="alert" className="rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                The laptop&apos;s network address is unknown, so this URL says localhost. Start with
                <code className="mx-1">.\demo.ps1 up</code> while on Wi-Fi to get a reachable address.
              </p>
            )}
            <ol className="list-decimal space-y-2 pl-5 text-xs text-slate-300">
              <li>Join the phone to the same Wi-Fi as this laptop.</li>
              <li>Open an RTMP broadcast app (for example Larix Broadcaster) and add a connection with the URL below.</li>
              <li>Start broadcasting. The camera turns to processing within a few seconds.</li>
              <li>Draw the zone people must not enter, then walk into it.</li>
            </ol>
            <CopyField label="Full RTMP URL" value={result.publish.rtmpUrl} />
            <p className="text-[11px] text-slate-500">
              This credential can only send video to phone cameras; it cannot watch any camera.
            </p>
            <div className="flex gap-2">
              <Link href={`/sources/${result.source.id}/zones`}
                className="flex-1 rounded-lg bg-emerald-500 px-3 py-2 text-center text-sm font-semibold text-slate-950 hover:bg-emerald-400">
                Draw zones on this camera
              </Link>
              <button onClick={onClose} className="rounded-lg border border-[color:var(--border)] px-3 py-2 text-sm text-slate-200">Done</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
