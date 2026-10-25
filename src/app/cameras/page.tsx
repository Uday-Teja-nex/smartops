"use client";

import { useEffect, useState } from "react";
import { useSmartOps } from "@/app/providers";
import { SectionHeader } from "@/components/SectionHeader";
import { LiveVideo } from "@/components/LiveVideo";
import Link from "next/link";
import { useAuth } from "@/app/auth";

export default function CameraViewPage() {
  const { sources, observations, selectedBuildingId } = useSmartOps();
  const { hasRole } = useAuth();
  const [now, setNow] = useState(0);
  const [mode, setMode] = useState<"live" | "matched">("live");
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, []);
  const visible = sources.filter((source) => source.buildingId === selectedBuildingId && source.sourceType === "rtsp");
  return <div className="space-y-6">
    <SectionHeader title="Camera view" subtitle={mode === "live" ? "Live video with the latest measured detections. Detection age is shown on each tile." : "Sampled frames with exactly matching boxes. Anonymous track IDs are temporary; no identity recognition."} />
    <div className="flex gap-3">
      <button onClick={() => setMode("live")} aria-pressed={mode === "live"} className="rounded-lg border border-slate-600 px-4 py-2 aria-pressed:bg-slate-700">Live video</button>
      <button onClick={() => setMode("matched")} aria-pressed={mode === "matched"} className="rounded-lg border border-slate-600 px-4 py-2 aria-pressed:bg-slate-700">Matched detection frames</button>
    </div>
    {visible.length === 0 && <p className="rounded-2xl border border-slate-700 p-8 text-slate-300">No RTSP sources in this building.</p>}
    <div className="grid gap-6 xl:grid-cols-2">
      {visible.map((source) => {
        const observation = observations[source.id];
        const age = observation ? Math.max(0, now - Date.parse(observation.capturedAt)) : Infinity;
        const fresh = now > 0 && age < 3000 && source.enabled && source.status !== "paused";
        return <section key={source.id} className="overflow-hidden rounded-2xl border border-slate-700 bg-slate-900">
          <div className="flex justify-between gap-4 p-4"><h2 className="font-semibold">{source.name}</h2>
            <span className={fresh ? "text-emerald-300" : "text-amber-300"}>{fresh ? `Detections ${(age / 1000).toFixed(1)}s old` : "No fresh observation"}</span></div>
          <div className="relative bg-slate-950" style={{ aspectRatio: observation ? `${observation.width}/${observation.height}` : "16/9" }}>
          {mode === "live" && source.enabled && source.status !== "paused" && <LiveVideo key={`${source.id}:${source.sourceUri}`} sourceId={source.id} />}
          {fresh && observation.previewJpeg ? <svg viewBox="0 0 1000 1000" preserveAspectRatio="none"
            className="pointer-events-none absolute inset-0 h-full w-full" role="img" aria-label={`${source.name}: real detections and configured zones`}>
            {mode === "matched" && <image href={`data:image/jpeg;base64,${observation.previewJpeg}`} width="1000" height="1000" preserveAspectRatio="none" />}
            {source.detectionConfig.zones?.map((zone) => <polygon key={zone.id}
              points={zone.polygon.map(([x, y]) => `${x * 1000},${y * 1000}`).join(" ")}
              fill="#38bdf822" stroke="#38bdf8" strokeWidth="3" />)}
            {observation.detections.map((detection, index) => <g key={index}>
              <rect x={detection.bbox.x * 1000} y={detection.bbox.y * 1000} width={detection.bbox.w * 1000}
                height={detection.bbox.h * 1000} fill="none" stroke="#34d399" strokeWidth="3" />
              <text x={detection.bbox.x * 1000} y={Math.max(24, detection.bbox.y * 1000)} fill="white" stroke="black" strokeWidth=".7" fontSize="24">
                {detection.label} {Math.round(detection.confidence * 100)}%
              </text>
            </g>)}
            {observation.tracks.map((track) => <text key={track.track_id} x={track.x * 1000} y={track.y * 1000}
              fill="#fde047" stroke="black" strokeWidth=".7" fontSize="24">#{track.track_id}</text>)}
          </svg> : mode === "matched" ? <div className="flex h-full items-center justify-center text-slate-400">Waiting for fresh processed frames</div> : null}
          {(!source.enabled || source.status === "paused") && mode === "live" && <div className="flex h-full items-center justify-center text-slate-400">Source paused or disabled</div>}
          </div>
          <p className="p-4 text-sm text-slate-400">{source.floor} · {source.zone} · {fresh ? `${observation.tracks.length} currently observed tracks` : "Track count unavailable"}</p>
          {hasRole("supervisor") && <Link className="block px-4 pb-4 text-sm text-cyan-300" href={`/sources/${source.id}/zones`}>Draw zones and configure rules</Link>}
        </section>;
      })}
    </div>
  </div>;
}
