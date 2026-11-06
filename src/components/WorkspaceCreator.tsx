"use client";

import { FormEvent, useEffect, useState } from "react";
import { Building, Plus } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { createWorkspace, fetchWorkspaceCapabilities, WorkspaceCapabilities, WorkspaceCreated } from "@/lib/api";

const inputClass =
  "mt-1 w-full rounded-lg border border-[color:var(--glass-border)] bg-white/5 px-2.5 py-1.5 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-[color:var(--accent)]";

/** "G: Food court queue, Main entrance" per line -> floors with zones. */
export const parseFloors = (text: string) =>
  text.split("\n").map((line) => line.trim()).filter(Boolean).map((line) => {
    const [head, rest = ""] = line.split(":");
    const level = head.trim().slice(0, 32);
    return { level, name: `Level ${level}`, zones: rest.split(",").map((zone) => zone.trim()).filter(Boolean) };
  });

export const WorkspaceCreator = () => {
  const [caps, setCaps] = useState<WorkspaceCapabilities | null>(null);
  const [name, setName] = useState("");
  const [accent, setAccent] = useState("#f97316");
  const [buildingName, setBuildingName] = useState("");
  const [floors, setFloors] = useState("G: Main entrance, Checkout queue\nL1: Food court");
  const [password, setPassword] = useState("");
  const [copyCameraId, setCopyCameraId] = useState("");
  const [addPhone, setAddPhone] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<WorkspaceCreated | null>(null);

  useEffect(() => {
    let active = true;
    fetchWorkspaceCapabilities().then((next) => {
      if (!active) return;
      setCaps(next);
      setCopyCameraId(next.copyableCameras[0]?.id ?? "");
    }).catch(() => { if (active) setCaps({ canCreateWorkspaces: false, copyableCameras: [] }); });
    return () => { active = false; };
  }, []);

  if (!caps?.canCreateWorkspaces) return null;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setCreated(await createWorkspace({
        name: name.trim(), accent, buildingName: buildingName.trim() || name.trim(),
        floors: parseFloors(floors), password, copyCameraId: copyCameraId || undefined, addPhoneCamera: addPhone,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the workspace");
    } finally {
      setBusy(false);
    }
  };

  return (
    <GlassPanel className="xl:col-span-2">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
        <Building className="h-4 w-4 text-[color:var(--accent)]" /> Client workspaces
      </h3>
      <p className="mt-1 text-[11px] text-slate-500">
        Create a separate, isolated workspace for a prospect: their name and colour, their floors and zones, and
        optionally a copy of a recorded camera (same stream and zones) so it shows live incidents right away.
      </p>
      {created ? (
        <div role="status" className="mt-4 space-y-2 rounded-xl bg-emerald-500/10 p-4 text-sm text-emerald-100">
          <p className="font-semibold">Workspace “{created.name}” is ready.</p>
          <p className="text-xs">Sign out and sign in with one of these (the password you chose):</p>
          <ul className="list-disc pl-5 font-mono text-xs">
            {created.accounts.map((account) => <li key={account.email}>{account.email} ({account.role})</li>)}
          </ul>
          {created.cameras.length > 0 && <p className="text-xs">Cameras: {created.cameras.join(", ")}</p>}
          <Button size="sm" onClick={() => { setCreated(null); setName(""); setPassword(""); }}>Create another</Button>
        </div>
      ) : (
        <form onSubmit={(event) => void submit(event)} className="mt-4 grid gap-3 md:grid-cols-2">
          <label className="text-xs text-slate-400">Client name
            <input required minLength={2} maxLength={120} className={inputClass} value={name}
              placeholder="Acme Mall" onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="text-xs text-slate-400">Brand colour
            <span className="mt-1 flex items-center gap-2">
              <input type="color" aria-label="Brand colour" value={accent} onChange={(e) => setAccent(e.target.value)}
                className="h-8 w-12 cursor-pointer rounded border border-[color:var(--glass-border)] bg-transparent" />
              <code className="text-xs text-slate-300">{accent}</code>
            </span>
          </label>
          <label className="text-xs text-slate-400">Building name
            <input maxLength={120} className={inputClass} value={buildingName}
              placeholder="Acme Mall East" onChange={(e) => setBuildingName(e.target.value)} />
          </label>
          <label className="text-xs text-slate-400">Demo password for the new accounts (10+ characters)
            <input required minLength={10} type="password" autoComplete="new-password" className={inputClass}
              value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          <label className="text-xs text-slate-400 md:col-span-2">Floors and zones (one floor per line: “Level: zone, zone”)
            <textarea rows={3} className={`${inputClass} font-mono`} value={floors} onChange={(e) => setFloors(e.target.value)} />
          </label>
          <label className="text-xs text-slate-400">Copy a recorded camera
            <select className={inputClass} value={copyCameraId} onChange={(e) => setCopyCameraId(e.target.value)}>
              <option value="">None</option>
              {caps.copyableCameras.map((camera) => (
                <option key={camera.id} value={camera.id}>{camera.name} ({camera.workspace}, {camera.zones} zones)</option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 self-end text-xs text-slate-400">
            <input type="checkbox" checked={addPhone} onChange={(e) => setAddPhone(e.target.checked)} />
            Add a phone camera slot
          </label>
          {error && <p role="alert" className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-200 md:col-span-2">{error}</p>}
          <div className="md:col-span-2">
            <Button type="submit" variant="primary" size="sm" disabled={busy || parseFloors(floors).length === 0}
              icon={<Plus className="h-3.5 w-3.5" />}>
              {busy ? "Creating…" : "Create workspace"}
            </Button>
          </div>
        </form>
      )}
    </GlassPanel>
  );
};
