"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Bell,
  Building2,
  Cpu,
  Save,
  SlidersHorizontal,
  Users,
} from "lucide-react";
import { useAuth } from "@/app/auth";
import { SectionHeader } from "@/components/SectionHeader";
import { Button } from "@/components/ui/Button";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { SkeletonPanel } from "@/components/ui/Skeleton";
import {
  fetchOrg,
  fetchRuntimeConfig,
  fetchUsers,
  OrgInfo,
  RuntimeConfig,
  updateOrgSettings,
} from "@/lib/api";
import { UserRecord } from "@/lib/types";

const CATEGORY_KEYS = [
  "Safety",
  "Housekeeping",
  "Occupancy",
  "Security",
  "Queue & Crowd",
  "System Health",
];

type Thresholds = Record<string, number>;

export default function SettingsPage() {
  const { hasRole } = useAuth();
  const isAdmin = hasRole("admin");
  const canEdit = hasRole("supervisor");

  const [org, setOrg] = useState<OrgInfo | null>(null);
  const [config, setConfig] = useState<RuntimeConfig | null>(null);
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  const [thresholds, setThresholds] = useState<Thresholds>({});
  const [notifyEmail, setNotifyEmail] = useState(false);
  const [notifyWebhook, setNotifyWebhook] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const [orgInfo, runtimeConfig] = await Promise.all([
          fetchOrg(),
          fetchRuntimeConfig(),
        ]);
        setOrg(orgInfo);
        setConfig(runtimeConfig);
        const settings = orgInfo.settings as {
          categoryThresholds?: Thresholds;
          notificationPreferences?: { email?: boolean; webhook?: boolean };
        };
        setThresholds(settings.categoryThresholds ?? {});
        setNotifyEmail(Boolean(settings.notificationPreferences?.email));
        setNotifyWebhook(Boolean(settings.notificationPreferences?.webhook));
        if (isAdmin) {
          setUsers(await fetchUsers());
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load settings");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [isAdmin]);

  const save = useCallback(async () => {
    setBusy(true);
    setSaved(false);
    setError(null);
    try {
      const next = await updateOrgSettings({
        categoryThresholds: thresholds,
        notificationPreferences: { email: notifyEmail, webhook: notifyWebhook },
      });
      setOrg(next);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }, [thresholds, notifyEmail, notifyWebhook]);

  if (loading) {
    return (
      <div className="space-y-4">
        <SkeletonPanel lines={3} />
        <SkeletonPanel lines={5} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Settings & Administration"
        subtitle="Organization profile, model runtime, review thresholds, and notification preferences"
        action={
          canEdit ? (
            <Button
              variant="primary"
              size="sm"
              disabled={busy}
              icon={<Save className="h-3.5 w-3.5" />}
              onClick={() => void save()}
            >
              {busy ? "Saving…" : saved ? "Saved ✓" : "Save changes"}
            </Button>
          ) : undefined
        }
      />

      {error && (
        <GlassPanel className="border-rose-500/25 text-sm text-rose-200">{error}</GlassPanel>
      )}

      <div className="grid gap-6 xl:grid-cols-2">
        <GlassPanel>
          <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
            <Building2 className="h-4 w-4 text-[color:var(--accent)]" /> Organization
          </h3>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Name</dt>
              <dd className="font-semibold text-slate-200">{org?.name ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Slug</dt>
              <dd className="font-mono text-xs text-slate-300">{org?.slug ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Tenant ID</dt>
              <dd className="font-mono text-xs text-slate-300">{org?.id ?? "—"}</dd>
            </div>
          </dl>
        </GlassPanel>

        <GlassPanel>
          <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
            <Cpu className="h-4 w-4 text-[color:var(--accent)]" /> Model runtime
          </h3>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Provider</dt>
              <dd className="font-mono text-xs text-slate-300">
                {config?.modelProvider ?? "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Orchestrator</dt>
              <dd className="font-mono text-xs text-slate-300">
                {config?.orchestrator ?? "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Evidence storage</dt>
              <dd className="font-mono text-xs text-slate-300">
                {config?.evidenceStorageEnabled ? "enabled (MinIO/S3)" : "disabled"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Evidence URL TTL</dt>
              <dd className="font-mono text-xs text-slate-300">
                {config ? `${config.evidenceUrlTtlSeconds}s` : "—"}
              </dd>
            </div>
          </dl>
          <p className="mt-4 text-[11px] leading-relaxed text-slate-600">
            Model selection is configured per deployment via environment variables
            (SMARTOPS_TEXT_MODEL, SMARTOPS_VISION_MODEL, SMARTOPS_DETECTOR_BACKEND).
            Hosted providers plug in through the same provider abstraction.
          </p>
        </GlassPanel>

        <GlassPanel>
          <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
            <SlidersHorizontal className="h-4 w-4 text-[color:var(--accent)]" />
            Category review thresholds
          </h3>
          <p className="mt-1 text-[11px] text-slate-600">
            Minimum model confidence per category before an incident skips human
            review. Empty uses the global default (0.6).
          </p>
          <div className="mt-4 space-y-3">
            {CATEGORY_KEYS.map((category) => (
              <label key={category} className="flex items-center justify-between gap-3 text-sm">
                <span className="text-slate-400">{category}</span>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  disabled={!canEdit}
                  value={thresholds[category] ?? ""}
                  placeholder="0.60"
                  onChange={(event) =>
                    setThresholds((prev) => {
                      const next = { ...prev };
                      const value = event.target.value;
                      if (value === "") delete next[category];
                      else next[category] = Number(value);
                      return next;
                    })
                  }
                  className="w-24 rounded-lg border border-[color:var(--glass-border)] bg-white/5 px-2.5 py-1.5 text-right font-mono text-xs text-slate-200 focus:outline-none disabled:opacity-50"
                />
              </label>
            ))}
          </div>
        </GlassPanel>

        <GlassPanel>
          <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
            <Bell className="h-4 w-4 text-[color:var(--accent)]" /> Notifications
          </h3>
          <p className="mt-1 text-[11px] text-slate-600">
            Preferences are stored per organization; delivery integrations are a
            deployment-readiness item.
          </p>
          <div className="mt-4 space-y-3">
            <label className="flex items-center justify-between text-sm">
              <span className="text-slate-400">Email digests</span>
              <input
                type="checkbox"
                disabled={!canEdit}
                checked={notifyEmail}
                onChange={(event) => setNotifyEmail(event.target.checked)}
                className="h-4 w-4 accent-[color:var(--accent-strong)]"
              />
            </label>
            <label className="flex items-center justify-between text-sm">
              <span className="text-slate-400">Webhook on critical incidents</span>
              <input
                type="checkbox"
                disabled={!canEdit}
                checked={notifyWebhook}
                onChange={(event) => setNotifyWebhook(event.target.checked)}
                className="h-4 w-4 accent-[color:var(--accent-strong)]"
              />
            </label>
          </div>
        </GlassPanel>

        {isAdmin && (
          <GlassPanel className="xl:col-span-2">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
              <Users className="h-4 w-4 text-[color:var(--accent)]" /> Users
            </h3>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-[11px] uppercase tracking-wide text-slate-600">
                  <tr>
                    <th className="pb-2 pr-4">Name</th>
                    <th className="pb-2 pr-4">Email</th>
                    <th className="pb-2 pr-4">Role</th>
                    <th className="pb-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {users.map((item) => (
                    <tr key={item.id}>
                      <td className="py-2.5 pr-4 font-semibold text-slate-200">
                        {item.name}
                      </td>
                      <td className="py-2.5 pr-4 font-mono text-xs text-slate-400">
                        {item.email}
                      </td>
                      <td className="py-2.5 pr-4">
                        <span className="rounded-full bg-[color:var(--accent-soft)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[color:var(--accent)]">
                          {item.role}
                        </span>
                      </td>
                      <td className="py-2.5 text-xs text-slate-400">
                        {item.active ? "Active" : "Disabled"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-[11px] text-slate-600">
              Seeded demo users (shared password, local development only). Invitations
              and password management are tracked in docs/DEPLOYMENT_READINESS.md.
            </p>
          </GlassPanel>
        )}
      </div>
    </div>
  );
}
