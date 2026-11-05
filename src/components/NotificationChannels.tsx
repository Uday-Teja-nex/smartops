"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Bell, Plus, Send, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { GlassPanel } from "@/components/ui/GlassPanel";
import {
  createNotificationChannel,
  deleteNotificationChannel,
  fetchNotificationChannels,
  fetchNotificationDeliveries,
  NotificationChannel,
  NotificationDelivery,
  NotificationSeverity,
  testNotificationChannel,
  updateNotificationChannel,
} from "@/lib/api";

const CATEGORIES = ["Security", "Safety", "Queue & Crowd", "Occupancy", "Housekeeping", "System Health"];
const SEVERITIES: NotificationSeverity[] = ["low", "medium", "high", "critical"];
const inputClass =
  "w-full rounded-lg border border-[color:var(--glass-border)] bg-white/5 px-2.5 py-1.5 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-[color:var(--accent)]";

const browserTimezone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
};

type Draft = {
  kind: "telegram" | "webhook";
  name: string;
  minSeverity: NotificationSeverity;
  categories: string[];
  limitHours: boolean;
  start: string;
  end: string;
  botToken: string;
  chatId: string;
  url: string;
  secret: string;
};

const emptyDraft = (): Draft => ({
  kind: "telegram", name: "", minSeverity: "high", categories: [], limitHours: false,
  start: "18:00", end: "08:00", botToken: "", chatId: "", url: "", secret: "",
});

const describeRule = (channel: NotificationChannel) => {
  const parts = [`${channel.minSeverity} and above`];
  parts.push(channel.categories.length ? channel.categories.join(", ") : "all categories");
  if (channel.activeHours) {
    parts.push(`${channel.activeHours.start}–${channel.activeHours.end} ${channel.activeHours.timezone}`);
  } else {
    parts.push("any time");
  }
  return parts.join(" · ");
};

export const NotificationChannels = ({ canManage }: { canManage: boolean }) => {
  const [channels, setChannels] = useState<NotificationChannel[] | null>(null);
  const [deliveries, setDeliveries] = useState<NotificationDelivery[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const [version, setVersion] = useState(0);
  const load = useCallback(() => setVersion((value) => value + 1), []);

  useEffect(() => {
    let active = true;
    Promise.all([fetchNotificationChannels(), fetchNotificationDeliveries()])
      .then(([nextChannels, nextDeliveries]) => {
        if (!active) return;
        setChannels(nextChannels);
        setDeliveries(nextDeliveries);
        setError(null);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Could not load notification channels");
      });
    return () => {
      active = false;
    };
  }, [version]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!draft) return;
    setBusy("create");
    setError(null);
    try {
      await createNotificationChannel({
        kind: draft.kind,
        name: draft.name.trim(),
        minSeverity: draft.minSeverity,
        categories: draft.categories,
        activeHours: draft.limitHours ? { start: draft.start, end: draft.end, timezone: browserTimezone() } : null,
        config: draft.kind === "telegram"
          ? { botToken: draft.botToken.trim(), chatId: draft.chatId.trim() }
          : { url: draft.url.trim(), ...(draft.secret.trim() ? { secret: draft.secret.trim() } : {}) },
      });
      setDraft(null);
      setNotice("Channel saved. Use “Send test” to confirm it reaches the destination.");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the channel");
    } finally {
      setBusy(null);
    }
  };

  const runTest = async (channel: NotificationChannel) => {
    setBusy(channel.id);
    setNotice(null);
    setError(null);
    try {
      const result = await testNotificationChannel(channel.id);
      if (result.delivered) setNotice(`Test message delivered to ${channel.name}.`);
      else setError(`Test to ${channel.name} failed: ${result.error ?? "unknown error"}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test failed");
    } finally {
      setBusy(null);
    }
  };

  const toggle = async (channel: NotificationChannel) => {
    setBusy(channel.id);
    try {
      await updateNotificationChannel(channel.id, { enabled: !channel.enabled });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(null);
    }
  };

  const remove = async (channel: NotificationChannel) => {
    if (!window.confirm(`Delete notification channel "${channel.name}"? Its delivery history is removed too.`)) return;
    setBusy(channel.id);
    try {
      await deleteNotificationChannel(channel.id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(null);
    }
  };

  const recent = (channelId: string) => deliveries.filter((item) => item.channelId === channelId);

  return (
    <GlassPanel className="xl:col-span-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
          <Bell className="h-4 w-4 text-[color:var(--accent)]" /> Notifications
        </h3>
        {canManage && !draft && (
          <Button size="sm" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => setDraft(emptyDraft())}>
            Add channel
          </Button>
        )}
      </div>
      <p className="mt-1 text-[11px] text-slate-500">
        New incidents that match a channel&apos;s rule are sent once, with retries if the destination is down.
        Bot tokens and webhook secrets are stored server-side and never shown again.
      </p>

      {error && <p role="alert" className="mt-3 rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-200">{error}</p>}
      {notice && <p role="status" className="mt-3 rounded-lg bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">{notice}</p>}

      {draft && (
        <form onSubmit={(event) => void submit(event)} className="mt-4 grid gap-3 rounded-xl border border-[color:var(--glass-border)] p-4 md:grid-cols-2">
          <label className="text-xs text-slate-400">
            Type
            <select className={`${inputClass} mt-1`} value={draft.kind}
              onChange={(event) => setDraft({ ...draft, kind: event.target.value as Draft["kind"] })}>
              <option value="telegram">Telegram bot</option>
              <option value="webhook">Webhook (JSON POST)</option>
            </select>
          </label>
          <label className="text-xs text-slate-400">
            Name
            <input required maxLength={120} className={`${inputClass} mt-1`} value={draft.name}
              placeholder="Night shift phone" onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
          </label>
          {draft.kind === "telegram" ? (
            <>
              <label className="text-xs text-slate-400">
                Bot token
                <input required type="password" autoComplete="off" className={`${inputClass} mt-1 font-mono`}
                  value={draft.botToken} onChange={(event) => setDraft({ ...draft, botToken: event.target.value })} />
              </label>
              <label className="text-xs text-slate-400">
                Chat ID
                <input required className={`${inputClass} mt-1 font-mono`} value={draft.chatId}
                  onChange={(event) => setDraft({ ...draft, chatId: event.target.value })} />
              </label>
            </>
          ) : (
            <>
              <label className="text-xs text-slate-400">
                URL
                <input required type="url" className={`${inputClass} mt-1 font-mono`} value={draft.url}
                  placeholder="https://" onChange={(event) => setDraft({ ...draft, url: event.target.value })} />
              </label>
              <label className="text-xs text-slate-400">
                Signing secret (optional, HMAC-SHA256 header)
                <input type="password" autoComplete="off" className={`${inputClass} mt-1 font-mono`}
                  value={draft.secret} onChange={(event) => setDraft({ ...draft, secret: event.target.value })} />
              </label>
            </>
          )}
          <label className="text-xs text-slate-400">
            Minimum severity
            <select className={`${inputClass} mt-1`} value={draft.minSeverity}
              onChange={(event) => setDraft({ ...draft, minSeverity: event.target.value as NotificationSeverity })}>
              {SEVERITIES.map((severity) => <option key={severity} value={severity}>{severity} and above</option>)}
            </select>
          </label>
          <fieldset className="text-xs text-slate-400">
            <legend>Categories (none selected = all)</legend>
            <div className="mt-1 flex flex-wrap gap-2">
              {CATEGORIES.map((category) => (
                <label key={category} className="flex items-center gap-1.5 rounded-full bg-white/5 px-2 py-1">
                  <input type="checkbox" checked={draft.categories.includes(category)}
                    onChange={(event) => setDraft({
                      ...draft,
                      categories: event.target.checked
                        ? [...draft.categories, category]
                        : draft.categories.filter((item) => item !== category),
                    })} />
                  {category}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="text-xs text-slate-400 md:col-span-2">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={draft.limitHours}
                onChange={(event) => setDraft({ ...draft, limitHours: event.target.checked })} />
              Only during these hours ({browserTimezone()})
            </label>
            {draft.limitHours && (
              <div className="mt-2 flex items-center gap-2">
                <input type="time" required className={`${inputClass} w-32`} value={draft.start}
                  onChange={(event) => setDraft({ ...draft, start: event.target.value })} />
                <span>to</span>
                <input type="time" required className={`${inputClass} w-32`} value={draft.end}
                  onChange={(event) => setDraft({ ...draft, end: event.target.value })} />
              </div>
            )}
          </div>
          <div className="flex gap-2 md:col-span-2">
            <Button type="submit" variant="primary" size="sm" disabled={busy === "create"}>
              {busy === "create" ? "Saving…" : "Save channel"}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setDraft(null)}>Cancel</Button>
          </div>
        </form>
      )}

      <div className="mt-4 space-y-2">
        {channels === null && !error && <p className="text-xs text-slate-500">Loading channels…</p>}
        {channels?.length === 0 && (
          <p className="rounded-lg border border-dashed border-[color:var(--glass-border)] px-3 py-4 text-center text-xs text-slate-500">
            No notification channels yet. Incidents appear in the console only.
          </p>
        )}
        {channels?.map((channel) => {
          const history = recent(channel.id);
          const sent = history.filter((item) => item.status === "sent").length;
          const failed = history.filter((item) => item.status === "dead");
          const pending = history.filter((item) => item.status === "pending").length;
          return (
            <div key={channel.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-white/[0.03] px-3 py-2.5">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-slate-200">
                  {channel.name}
                  <span className="ml-2 rounded-full bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
                    {channel.kind}
                  </span>
                  {!channel.enabled && <span className="ml-2 text-[11px] text-amber-300">Paused</span>}
                </p>
                <p className="text-[11px] text-slate-500">{channel.destination} · {describeRule(channel)}</p>
                <p className="text-[11px] text-slate-500">
                  Last 100: {sent} sent{pending ? `, ${pending} retrying` : ""}
                  {failed.length ? (
                    <span className="text-rose-300">, {failed.length} failed ({failed[0].lastError})</span>
                  ) : null}
                </p>
              </div>
              {canManage && (
                <div className="flex gap-1.5">
                  <Button size="sm" icon={<Send className="h-3.5 w-3.5" />} disabled={busy === channel.id}
                    onClick={() => void runTest(channel)}>
                    {busy === channel.id ? "Sending…" : "Send test"}
                  </Button>
                  <Button size="sm" variant="ghost" disabled={busy === channel.id} onClick={() => void toggle(channel)}>
                    {channel.enabled ? "Pause" : "Resume"}
                  </Button>
                  <Button size="sm" variant="danger" aria-label={`Delete ${channel.name}`} disabled={busy === channel.id}
                    icon={<Trash2 className="h-3.5 w-3.5" />} onClick={() => void remove(channel)} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </GlassPanel>
  );
};
