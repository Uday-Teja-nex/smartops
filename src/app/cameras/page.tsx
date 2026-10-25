"use client";

import { useEffect, useState } from "react";
import { useSmartOps } from "@/app/providers";
import { SectionHeader } from "@/components/SectionHeader";

export default function CameraViewPage() {
  const { sources, observations, selectedBuildingId } = useSmartOps();
  const [now, setNow] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, []);
  const visible = sources.filter((source) => source.buildingId === selectedBuildingId && source.sourceType === "rtsp");
  return <div className="space-y-6">
    <SectionHeader title="Camera view" subtitle="Sampled processing preview. Boxes and zones match the displayed frame; this is not full-rate live video." />
    {visible.length === 0 && <p className="rounded-2xl border border-slate-700 p-8 text-slate-300">No RTSP sources in this building.</p>}
    <div className="grid gap-6 xl:grid-cols-2">
      {visible.map((source) => {
        const observation = observations[source.id];
        const age = observation ? Math.max(0, now - Date.parse(observation.capturedAt)) : Infinity;
        const fresh = now > 0 && age < 3000 && source.enabled && source.status !== "paused";
        return <section key={source.id} className="overflow-hidden rounded-2xl border border-slate-700 bg-slate-900">
          <div className="flex justify-between gap-4 p-4"><h2 className="font-semibold">{source.name}</h2>
            <span className={fresh ? "text-emerald-300" : "text-amber-300"}>{fresh ? `${(age / 1000).toFixed(1)}s ago` : "No fresh observation"}</span></div>
          {fresh && observation.previewJpeg ? <svg viewBox="0 0 1000 1000" preserveAspectRatio="none"
            style={{ aspectRatio: `${observation.width}/${observation.height}` }} className="w-full" role="img" aria-label={`${source.name}: real detections and configured zones`}>
            <image href={`data:image/jpeg;base64,${observation.previewJpeg}`} width="1000" height="1000" preserveAspectRatio="none" />
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
          </svg> : <div className="flex aspect-video items-center justify-center bg-slate-950 text-slate-400">Waiting for fresh processed frames</div>}
          <p className="p-4 text-sm text-slate-400">{source.floor} · {source.zone} · {fresh ? `${observation.tracks.length} currently observed tracks` : "Track count unavailable"}</p>
        </section>;
      })}
    </div>
  </div>;
}
