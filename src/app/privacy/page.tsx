"use client";

import { FormEvent, useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "@/app/auth";
import { SectionHeader } from "@/components/SectionHeader";
import { Button } from "@/components/ui/Button";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { fetchOrg, OrgInfo, updateOrgSettings } from "@/lib/api";

const DEFAULT_RETENTION_DAYS = 30;

const Row = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <div className="border-t border-white/5 py-3 first:border-t-0">
    <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
    <div className="mt-1 text-sm leading-relaxed text-slate-400">{children}</div>
  </div>
);

export default function PrivacyPage() {
  const { hasRole } = useAuth();
  const [org, setOrg] = useState<OrgInfo | null>(null);
  const [days, setDays] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchOrg().then((next) => { if (active) setOrg(next); }).catch(() => { /* page still renders the policy */ });
    return () => { active = false; };
  }, []);

  const retention = typeof org?.settings?.evidenceRetentionDays === "number"
    ? org.settings.evidenceRetentionDays : DEFAULT_RETENTION_DAYS;

  const save = async (event: FormEvent) => {
    event.preventDefault();
    try {
      setOrg(await updateOrgSettings({ evidenceRetentionDays: Number(days) }));
      setMessage(`Evidence is now kept for ${days} days.`);
      setDays("");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not change retention");
    }
  };

  return (
    <div className="space-y-6">
      <SectionHeader title="How SmartOps handles data" subtitle={org ? `Workspace: ${org.name}` : "Data processing summary"} />
      <GlassPanel className="max-w-3xl">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
          <ShieldCheck className="h-4 w-4 text-[color:var(--accent)]" /> What is processed and stored
        </h2>
        <div className="mt-3">
          <Row title="No biometrics or identity">
            SmartOps detects people and objects as anonymous boxes. It does not do face recognition, identify anyone,
            or infer age, gender or other characteristics. Track numbers are temporary and are discarded when someone
            leaves the camera view.
          </Row>
          <Row title="What is stored">
            Incidents produced by zone rules (time, zone, rule, counts), the operator actions on them, and for each
            incident a snapshot and a 10-second clip around the event. Live video itself is not recorded.
          </Row>
          <Row title="How long evidence is kept">
            Snapshots and clips are deleted automatically after <strong className="text-slate-200">{retention} days</strong>.
            Incident records stay, and each incident&apos;s timeline notes when its evidence was deleted.
          </Row>
          <Row title="Who can see it">
            Only signed-in members of this workspace. Other workspaces cannot see any of it, enforced by the server.
            Evidence access is restricted by role, links expire after minutes, and every access is logged.
          </Row>
          <Row title="AI review">
            A vision model may describe an incident&apos;s clean snapshot to assist operators. It never changes the
            rule&apos;s decision, and its output is labelled with the model name. With a local model, images never
            leave this computer. If a hosted model is configured, the snapshot is sent to that provider.
          </Row>
          <Row title="Where it runs">
            On this computer, or on a server you control. Nothing is sent elsewhere except notifications you configure
            (Telegram, webhook) and, if enabled, hosted AI review.
          </Row>
        </div>
      </GlassPanel>
      {hasRole("admin") && (
        <GlassPanel className="max-w-3xl">
          <form onSubmit={(event) => void save(event)} className="flex flex-wrap items-end gap-3">
            <label className="text-xs text-slate-400">Evidence retention (days, 1–3650)
              <input required type="number" min={1} max={3650} value={days} placeholder={String(retention)}
                onChange={(e) => setDays(e.target.value)}
                className="mt-1 block w-32 rounded-lg border border-[color:var(--glass-border)] bg-white/5 px-3 py-2 text-sm text-slate-200" />
            </label>
            <Button type="submit" size="sm" variant="primary">Save retention</Button>
            <p className="w-full text-[11px] text-slate-500">
              Shortening retention deletes older snapshots and clips within the hour. This cannot be undone.
            </p>
            {message && <p role="status" className="w-full text-xs text-slate-300">{message}</p>}
          </form>
        </GlassPanel>
      )}
    </div>
  );
}
