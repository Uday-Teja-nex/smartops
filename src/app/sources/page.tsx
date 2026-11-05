"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import {
  Camera,
  CircleAlert,
  CirclePause,
  CirclePlay,
  CircleX,
  Pencil,
  Plus,
  Smartphone,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { useAuth } from "@/app/auth";
import { useSmartOps } from "@/app/providers";
import { PhoneCameraDialog } from "@/components/PhoneCameraDialog";
import { SectionHeader } from "@/components/SectionHeader";
import { Badge } from "@/components/Badge";
import {
  createSource,
  deleteSource,
  sourceAction,
  updateSource,
} from "@/lib/api";
import { SOURCE_STATUS_COLORS, hexToRgba } from "@/lib/visuals";
import { classNames, formatDateTime } from "@/lib/utils";
import {
  Building,
  DetectionConfig,
  SourceCreateInput,
  SourceRecord,
  SourceStatus,
  SourceType,
} from "@/lib/types";

const SOURCE_TYPE_OPTIONS: Array<{
  value: SourceType;
  label: string;
  supported: boolean;
  note: string;
}> = [
  {
    value: "file",
    label: "MP4 / file",
    supported: true,
    note: "Fully supported. Local footage in sample-data/input.",
  },
  {
    value: "rtsp",
    label: "RTSP stream",
    supported: true,
    note: "Continuous detection with polygon rules. Relay through MediaMTX for browser playback.",
  },
  {
    value: "onvif",
    label: "ONVIF camera",
    supported: false,
    note: "Adapter pending — source can be registered but will stay offline.",
  },
  {
    value: "webrtc",
    label: "WebRTC feed",
    supported: false,
    note: "Adapter pending — source can be registered but will stay offline.",
  },
];

const STATUS_LABELS: Record<SourceStatus, string> = {
  online: "Online",
  processing: "Processing",
  paused: "Paused",
  failing: "Failing",
  offline: "Offline",
};

type FormState = {
  detectionConfig: DetectionConfig;
  name: string;
  buildingId: string;
  floorId: string;
  zoneId: string;
  floor: string;
  zone: string;
  sourceType: SourceType;
  sourceUri: string;
  inputFormat: string;
  credentialsRef: string;
  enabled: boolean;
  tags: string;
  positionNotes: string;
  windowSeconds: string;
  sampleFramesPerWindow: string;
  minConfidence: string;
};

const emptyForm = (buildings: Building[]): FormState => ({
  detectionConfig: {},
  name: "",
  buildingId: buildings[0]?.id ?? "",
  floorId: "",
  zoneId: "",
  floor: "",
  zone: "",
  sourceType: "file",
  sourceUri: "",
  inputFormat: "mp4",
  credentialsRef: "",
  enabled: true,
  tags: "",
  positionNotes: "",
  windowSeconds: "30",
  sampleFramesPerWindow: "3",
  minConfidence: "0.35",
});

const formFromSource = (source: SourceRecord): FormState => ({
  detectionConfig: source.detectionConfig,
  name: source.name,
  buildingId: source.buildingId,
  floorId: source.floorId ?? "",
  zoneId: source.zoneId ?? "",
  floor: source.floor,
  zone: source.zone,
  sourceType: source.sourceType,
  sourceUri: source.sourceUri,
  inputFormat: source.inputFormat ?? "",
  credentialsRef: source.credentialsRef ?? "",
  enabled: source.enabled,
  tags: source.tags.join(", "),
  positionNotes: source.positionNotes ?? "",
  windowSeconds: String(source.detectionConfig.windowSeconds ?? 30),
  sampleFramesPerWindow: String(source.detectionConfig.sampleFramesPerWindow ?? 3),
  minConfidence: String(source.detectionConfig.minConfidence ?? 0.35),
});

const formToInput = (form: FormState): SourceCreateInput => ({
  name: form.name.trim(),
  buildingId: form.buildingId,
  floorId: form.floorId || null,
  zoneId: form.zoneId || null,
  floor: form.floor.trim() || null,
  zone: form.zone.trim() || null,
  sourceType: form.sourceType,
  sourceUri: form.sourceUri.trim(),
  inputFormat: form.inputFormat.trim() || null,
  credentialsRef: form.credentialsRef.trim() || null,
  enabled: form.enabled,
  tags: form.tags
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean),
  positionNotes: form.positionNotes.trim() || null,
  detectionConfig: {
    ...form.detectionConfig,
    windowSeconds: Number(form.windowSeconds) || 30,
    sampleFramesPerWindow: Number(form.sampleFramesPerWindow) || 3,
    minConfidence: Number(form.minConfidence) || 0.35,
  },
});

const SourceStatusPill = ({ status }: { status: SourceStatus }) => {
  const color = SOURCE_STATUS_COLORS[status] ?? "#64748b";
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold"
      style={{ backgroundColor: hexToRgba(color, 0.15), color }}
    >
      <span
        className={classNames(
          "h-1.5 w-1.5 rounded-full",
          (status === "online" || status === "processing") && "animate-pulse"
        )}
        style={{ backgroundColor: color }}
      />
      {STATUS_LABELS[status] ?? status}
    </span>
  );
};

export default function SourcesPage() {
  const { sources, buildings, backendStatus, refreshSources } = useSmartOps();
  const { hasRole } = useAuth();
  const canManage = hasRole("supervisor");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(() => emptyForm(buildings));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [phoneOpen, setPhoneOpen] = useState(false);

  const selectedBuilding = useMemo(
    () => buildings.find((building) => building.id === form.buildingId),
    [buildings, form.buildingId]
  );
  const floors = useMemo(
    () => selectedBuilding?.floors ?? [],
    [selectedBuilding]
  );
  const zones = useMemo(
    () => floors.find((floor) => floor.id === form.floorId)?.zones ?? [],
    [floors, form.floorId]
  );

  const visibleSources = useMemo(
    () =>
      statusFilter === "all"
        ? sources
        : sources.filter((source) => source.status === statusFilter),
    [sources, statusFilter]
  );

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const source of sources) {
      counts[source.status] = (counts[source.status] ?? 0) + 1;
    }
    return counts;
  }, [sources]);

  const openCreate = () => {
    setEditingId(null);
    setForm(emptyForm(buildings));
    setError(null);
    setDrawerOpen(true);
  };

  const openEdit = (source: SourceRecord) => {
    setEditingId(source.id);
    setForm(formFromSource(source));
    setError(null);
    setDrawerOpen(true);
  };

  const submit = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const input = formToInput(form);
      if (!input.name) throw new Error("Name is required");
      if (!input.sourceUri) throw new Error("Source URI is required");
      if (editingId) {
        await updateSource(editingId, input);
      } else {
        await createSource(input);
      }
      await refreshSources();
      setDrawerOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }, [editingId, form, refreshSources]);

  const runAction = useCallback(
    async (sourceId: string, action: "pause" | "resume" | "disable") => {
      setBusy(true);
      setError(null);
      try {
        await sourceAction(sourceId, action);
        await refreshSources();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Action failed");
      } finally {
        setBusy(false);
      }
    },
    [refreshSources]
  );

  const removeSource = useCallback(
    async (source: SourceRecord) => {
      if (
        !window.confirm(
          `Delete source "${source.name}"? Incidents that reference it are kept.`
        )
      ) {
        return;
      }
      setBusy(true);
      setError(null);
      try {
        await deleteSource(source.id);
        await refreshSources();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Delete failed");
      } finally {
        setBusy(false);
      }
    },
    [refreshSources]
  );

  return (
    <div className="space-y-6">
      {phoneOpen && (
        <PhoneCameraDialog buildings={buildings} onClose={() => setPhoneOpen(false)}
          onCreated={() => void refreshSources()} />
      )}
      <SectionHeader
        title="Source Management"
        subtitle="Register, monitor, and control every CCTV/video input across buildings"
        action={
          <div className="flex items-center gap-2">
            <button
              onClick={() => void refreshSources()}
              className="inline-flex items-center gap-2 rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-sm font-semibold text-slate-200 transition hover:bg-slate-800"
            >
              <RefreshCw className="h-4 w-4" /> Refresh
            </button>
            <button
              onClick={openCreate}
              disabled={!canManage}
              title={canManage ? undefined : "Requires supervisor role or higher"}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-3 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Plus className="h-4 w-4" /> Add source
            </button>
            <button
              onClick={() => setPhoneOpen(true)}
              disabled={!canManage}
              title={canManage ? undefined : "Requires supervisor role or higher"}
              className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm font-semibold text-emerald-200 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Smartphone className="h-4 w-4" /> Add phone camera
            </button>
          </div>
        }
      />

      {backendStatus !== "connected" && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          <CircleAlert className="h-4 w-4 shrink-0" />
          Backend is unreachable. Source management requires the API — start the
          Docker stack and refresh.
        </div>
      )}

      {error && (
        <div className="flex items-center gap-3 rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          <CircleAlert className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setStatusFilter("all")}
          className={classNames(
            "rounded-full px-3 py-1.5 text-xs font-semibold transition",
            statusFilter === "all"
              ? "bg-slate-200 text-slate-900"
              : "bg-slate-800/70 text-slate-300 hover:bg-slate-700"
          )}
        >
          All ({sources.length})
        </button>
        {(Object.keys(STATUS_LABELS) as SourceStatus[]).map((status) => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={classNames(
              "rounded-full px-3 py-1.5 text-xs font-semibold transition",
              statusFilter === status
                ? "bg-slate-200 text-slate-900"
                : "bg-slate-800/70 text-slate-300 hover:bg-slate-700"
            )}
          >
            {STATUS_LABELS[status]} ({statusCounts[status] ?? 0})
          </button>
        ))}
      </div>

      {visibleSources.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-[color:var(--border)] bg-[color:var(--surface)]/60 px-6 py-16 text-center">
          <Camera className="h-8 w-8 text-slate-500" />
          <p className="text-sm font-semibold text-slate-300">
            {sources.length === 0
              ? "No video sources registered yet"
              : "No sources match this filter"}
          </p>
          <p className="max-w-md text-xs text-slate-500">
            Add an MP4 source pointing at footage in sample-data/input to run the
            full pipeline locally. RTSP/ONVIF/WebRTC can be registered now and
            activated when their adapters land.
          </p>
          {sources.length === 0 && (
            <button
              onClick={openCreate}
              className="mt-2 inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-3 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400"
            >
              <Plus className="h-4 w-4" /> Add your first source
            </button>
          )}
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/80">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-[color:var(--border)] text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Location</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Health</th>
                <th className="px-4 py-3">Tags</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleSources.map((source) => {
                const building = buildings.find((b) => b.id === source.buildingId);
                const typeOption = SOURCE_TYPE_OPTIONS.find(
                  (option) => option.value === source.sourceType
                );
                return (
                  <tr
                    key={source.id}
                    className="border-b border-[color:var(--border)]/60 transition last:border-b-0 hover:bg-slate-800/30"
                  >
                    <td className="px-4 py-3">
                      <p className="font-semibold text-slate-200">{source.name}</p>
                      <p className="mt-0.5 max-w-[260px] truncate text-xs text-slate-500">
                        {source.sourceUri}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-slate-300">
                      <p>{building?.name ?? source.buildingId}</p>
                      <p className="text-xs text-slate-500">
                        {source.floor} · {source.zone}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <Badge
                        label={typeOption?.label ?? source.sourceType}
                        tone={typeOption?.supported ? "green" : "slate"}
                      />
                      {!typeOption?.supported && (
                        <p className="mt-1 text-[10px] text-slate-500">adapter pending</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <SourceStatusPill status={source.status} />
                      {!source.enabled && (
                        <p className="mt-1 text-[10px] uppercase tracking-wide text-slate-500">
                          disabled
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">
                      {source.health?.lastSeen ? (
                        <>
                          <p>seen {formatDateTime(String(source.health.lastSeen))}</p>
                          {source.health.lastError ? (
                            <p className="mt-0.5 max-w-[200px] truncate text-rose-300">
                              {String(source.health.lastError)}
                            </p>
                          ) : (
                            <p className="text-emerald-300">healthy</p>
                          )}
                        </>
                      ) : (
                        <p className="text-slate-600">no probe yet</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex max-w-[160px] flex-wrap gap-1">
                        {source.tags.map((tag) => (
                          <span
                            key={tag}
                            className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1.5">
                        {canManage && source.sourceType === "rtsp" && <Link className="rounded-lg px-2 py-1 text-xs text-cyan-300" href={`/sources/${source.id}/zones`}>Zones</Link>}
                        {source.status === "paused" || !source.enabled ? (
                          <button
                            title="Resume"
                            disabled={busy || !canManage}
                            onClick={() => void runAction(source.id, "resume")}
                            className="rounded-lg p-2 text-emerald-300 transition hover:bg-emerald-500/10"
                          >
                            <CirclePlay className="h-4 w-4" />
                          </button>
                        ) : (
                          <button
                            title="Pause"
                            disabled={busy || !canManage}
                            onClick={() => void runAction(source.id, "pause")}
                            className="rounded-lg p-2 text-amber-300 transition hover:bg-amber-500/10"
                          >
                            <CirclePause className="h-4 w-4" />
                          </button>
                        )}
                        <button
                          title="Disable"
                          disabled={busy || !canManage || !source.enabled}
                          onClick={() => void runAction(source.id, "disable")}
                          className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-500/10 disabled:opacity-40"
                        >
                          <CircleX className="h-4 w-4" />
                        </button>
                        <button
                          title="Edit"
                          disabled={busy || !canManage}
                          onClick={() => openEdit(source)}
                          className="rounded-lg p-2 text-sky-300 transition hover:bg-sky-500/10"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          title="Delete"
                          disabled={busy || !canManage}
                          onClick={() => void removeSource(source)}
                          className="rounded-lg p-2 text-rose-300 transition hover:bg-rose-500/10"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {drawerOpen && (
        <div className="fixed inset-0 z-40 flex justify-end bg-slate-950/60 backdrop-blur-sm">
          <div className="h-full w-full max-w-xl overflow-y-auto border-l border-[color:var(--border)] bg-[color:var(--surface)] p-6 shadow-2xl">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-100">
                {editingId ? "Edit source" : "Add video source"}
              </h2>
              <button
                onClick={() => setDrawerOpen(false)}
                className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-800"
              >
                <CircleX className="h-5 w-5" />
              </button>
            </div>

            <div className="mt-6 space-y-4">
              <label className="block text-sm">
                <span className="text-slate-400">Source name</span>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Lobby Atrium North"
                  className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                />
              </label>

              <div className="grid grid-cols-2 gap-3">
                <label className="block text-sm">
                  <span className="text-slate-400">Building</span>
                  <select
                    value={form.buildingId}
                    onChange={(e) =>
                      setForm({ ...form, buildingId: e.target.value, floorId: "", zoneId: "" })
                    }
                    className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                  >
                    {buildings.map((building) => (
                      <option key={building.id} value={building.id}>
                        {building.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm">
                  <span className="text-slate-400">Source type</span>
                  <select
                    value={form.sourceType}
                    onChange={(e) =>
                      setForm({ ...form, sourceType: e.target.value as SourceType })
                    }
                    className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                  >
                    {SOURCE_TYPE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                        {option.supported ? "" : " (adapter pending)"}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <p className="rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)]/60 px-3 py-2 text-xs text-slate-400">
                {SOURCE_TYPE_OPTIONS.find((o) => o.value === form.sourceType)?.note}
              </p>

              <div className="grid grid-cols-2 gap-3">
                <label className="block text-sm">
                  <span className="text-slate-400">Floor</span>
                  {floors.length > 0 ? (
                    <select
                      value={form.floorId}
                      onChange={(e) =>
                        setForm({ ...form, floorId: e.target.value, zoneId: "" })
                      }
                      className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                    >
                      <option value="">Custom label…</option>
                      {floors.map((floor) => (
                        <option key={floor.id} value={floor.id}>
                          {floor.level} — {floor.name}
                        </option>
                      ))}
                    </select>
                  ) : null}
                  {!form.floorId && (
                    <input
                      value={form.floor}
                      onChange={(e) => setForm({ ...form, floor: e.target.value })}
                      placeholder="L1"
                      className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                    />
                  )}
                </label>
                <label className="block text-sm">
                  <span className="text-slate-400">Zone / room</span>
                  {zones.length > 0 ? (
                    <select
                      value={form.zoneId}
                      onChange={(e) => setForm({ ...form, zoneId: e.target.value })}
                      className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                    >
                      <option value="">Custom label…</option>
                      {zones.map((zone) => (
                        <option key={zone.id} value={zone.id}>
                          {zone.name} ({zone.kind})
                        </option>
                      ))}
                    </select>
                  ) : null}
                  {!form.zoneId && (
                    <input
                      value={form.zone}
                      onChange={(e) => setForm({ ...form, zone: e.target.value })}
                      placeholder="Lobby Atrium"
                      className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                    />
                  )}
                </label>
              </div>

              <label className="block text-sm">
                <span className="text-slate-400">Source URI</span>
                <input
                  value={form.sourceUri}
                  onChange={(e) => setForm({ ...form, sourceUri: e.target.value })}
                  placeholder={
                    form.sourceType === "file"
                      ? "/app/sample-data/input/my-footage.mp4"
                      : "rtsp://host:554/stream"
                  }
                  className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 font-mono text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                />
              </label>

              <div className="grid grid-cols-2 gap-3">
                <label className="block text-sm">
                  <span className="text-slate-400">Input format</span>
                  <input
                    value={form.inputFormat}
                    onChange={(e) => setForm({ ...form, inputFormat: e.target.value })}
                    placeholder="mp4 / h264"
                    className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-slate-400">Credentials ref (placeholder)</span>
                  <input
                    value={form.credentialsRef}
                    onChange={(e) => setForm({ ...form, credentialsRef: e.target.value })}
                    placeholder="secret://vault/cam-01"
                    className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 font-mono text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                  />
                </label>
              </div>

              <label className="block text-sm">
                <span className="text-slate-400">Tags (comma separated)</span>
                <input
                  value={form.tags}
                  onChange={(e) => setForm({ ...form, tags: e.target.value })}
                  placeholder="lobby, entrance, priority"
                  className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                />
              </label>

              <label className="block text-sm">
                <span className="text-slate-400">Camera position notes</span>
                <textarea
                  value={form.positionNotes}
                  onChange={(e) => setForm({ ...form, positionNotes: e.target.value })}
                  rows={2}
                  placeholder="Mounted above the north entrance, facing the escalators."
                  className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                />
              </label>

              <fieldset className="rounded-xl border border-[color:var(--border)] p-3">
                <legend className="px-1 text-xs uppercase tracking-wide text-slate-500">
                  Detection configuration
                </legend>
                <div className="grid grid-cols-3 gap-3">
                  <label className="block text-sm">
                    <span className="text-xs text-slate-400">Window (s)</span>
                    <input
                      value={form.windowSeconds}
                      onChange={(e) => setForm({ ...form, windowSeconds: e.target.value })}
                      inputMode="numeric"
                      className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="text-xs text-slate-400">Frames / window</span>
                    <input
                      value={form.sampleFramesPerWindow}
                      onChange={(e) =>
                        setForm({ ...form, sampleFramesPerWindow: e.target.value })
                      }
                      inputMode="numeric"
                      className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="text-xs text-slate-400">Min confidence</span>
                    <input
                      value={form.minConfidence}
                      onChange={(e) => setForm({ ...form, minConfidence: e.target.value })}
                      inputMode="decimal"
                      className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                    />
                  </label>
                </div>
              </fieldset>

              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                  className="h-4 w-4 rounded border-slate-600 bg-slate-800 accent-emerald-500"
                />
                Enabled (ingestion picks this source up on the next scan)
              </label>

              {error && (
                <p className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                  {error}
                </p>
              )}

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  onClick={() => setDrawerOpen(false)}
                  className="rounded-lg border border-[color:var(--border)] px-4 py-2 text-sm font-semibold text-slate-300 transition hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  onClick={() => void submit()}
                  disabled={busy || !canManage}
                  className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:opacity-50"
                >
                  {busy ? "Saving…" : editingId ? "Save changes" : "Register source"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
