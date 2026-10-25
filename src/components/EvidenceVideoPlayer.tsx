"use client";

import { useMemo, useRef, useState } from "react";
import { Pause, Play, ScanEye } from "lucide-react";
import { DetectionRecord } from "@/lib/types";
import { classNames, formatConfidence } from "@/lib/utils";

/**
 * Overlay annotation derived from persisted detector output. Boxes are
 * normalized [0,1] and shown around their source frame timestamp.
 * There are intentionally no built-in demo annotations: if the backend has
 * no detections for a clip, the player says so instead of faking boxes.
 */
export type EvidenceAnnotation = {
  id: string;
  start: number;
  end: number;
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  confidence?: number;
};

/** Window (seconds) an annotation stays visible around its frame timestamp. */
const ANNOTATION_WINDOW = 0.9;

export const detectionsToAnnotations = (
  detections: DetectionRecord[],
  clipStartSeconds = 0
): EvidenceAnnotation[] =>
  detections.map((detection) => {
    const ts = Math.max(0, detection.frameTs - clipStartSeconds);
    return {
      id: detection.id,
      start: Math.max(0, ts - ANNOTATION_WINDOW),
      end: ts + ANNOTATION_WINDOW,
      x: detection.bbox.x,
      y: detection.bbox.y,
      w: detection.bbox.w,
      h: detection.bbox.h,
      label: detection.label,
      confidence: detection.confidence,
    };
  });

export const EvidenceVideoPlayer = ({
  src,
  sourceLabel,
  annotations = [],
  burnedInOverlays = false,
}: {
  src: string;
  sourceLabel?: string;
  annotations?: EvidenceAnnotation[];
  burnedInOverlays?: boolean;
}) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [showBoxes, setShowBoxes] = useState(true);
  const [error, setError] = useState(false);

  // Derived-state reset when the clip source changes (render-time pattern,
  // see react.dev "You Might Not Need an Effect").
  const [lastSrc, setLastSrc] = useState(src);
  if (lastSrc !== src) {
    setLastSrc(src);
    setError(false);
    setPlaying(false);
    setCurrentTime(0);
  }

  const activeAnnotations = useMemo(
    () =>
      showBoxes
        ? annotations.filter(
            (annotation) =>
              currentTime >= annotation.start && currentTime <= annotation.end
          )
        : [],
    [annotations, currentTime, showBoxes]
  );

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      void video.play();
    } else {
      video.pause();
    }
  };

  if (error) {
    return (
      <div className="mt-3 rounded-xl border border-[color:var(--glass-border)] bg-white/3 p-6 text-center text-xs text-slate-500">
        The evidence clip could not be loaded. It may have expired — reopen the
        incident to request a fresh evidence URL.
      </div>
    );
  }

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-[color:var(--glass-border)] bg-black/60">
      <div className="relative">
        <video
          ref={videoRef}
          src={src}
          className="aspect-video w-full bg-black"
          playsInline
          preload="metadata"
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
          onLoadedMetadata={(event) => setDuration(event.currentTarget.duration || 0)}
          onError={() => setError(true)}
        />

        {/* Real detection overlays (normalized bboxes from the detector). */}
        {activeAnnotations.map((annotation) => (
          <div
            key={annotation.id}
            className="pointer-events-none absolute rounded-md border-2 border-[color:var(--accent)] shadow-[0_0_20px_rgba(45,212,191,0.25)]"
            style={{
              left: `${annotation.x * 100}%`,
              top: `${annotation.y * 100}%`,
              width: `${annotation.w * 100}%`,
              height: `${annotation.h * 100}%`,
            }}
          >
            <span className="absolute -top-6 left-0 whitespace-nowrap rounded-md bg-black/80 px-1.5 py-0.5 text-[10px] font-semibold text-[color:var(--accent)]">
              {annotation.label}
              {annotation.confidence !== undefined &&
                ` · ${formatConfidence(annotation.confidence)}`}
            </span>
          </div>
        ))}

        <button
          type="button"
          onClick={togglePlay}
          className="absolute inset-0 flex items-center justify-center bg-transparent"
          aria-label={playing ? "Pause evidence clip" : "Play evidence clip"}
        >
          {!playing && (
            <span className="flex h-14 w-14 items-center justify-center rounded-full bg-black/60 text-white backdrop-blur transition hover:scale-105">
              <Play className="ml-1 h-6 w-6" />
            </span>
          )}
        </button>
      </div>

      <div className="flex items-center gap-3 border-t border-[color:var(--glass-border)] bg-white/3 px-3 py-2">
        <button
          type="button"
          onClick={togglePlay}
          className="rounded-lg p-1.5 text-slate-300 transition hover:bg-white/10"
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        </button>

        <input
          type="range"
          min={0}
          max={duration || 0}
          step={0.1}
          value={currentTime}
          onChange={(event) => {
            const next = Number(event.target.value);
            if (videoRef.current) videoRef.current.currentTime = next;
            setCurrentTime(next);
          }}
          className="h-1 flex-1 accent-[color:var(--accent-strong)]"
          aria-label="Seek"
        />

        <span className="w-20 text-right font-mono text-[10px] text-slate-500">
          {currentTime.toFixed(1)}s / {duration ? duration.toFixed(1) : "–"}s
        </span>

        {annotations.length > 0 ? (
          <button
            type="button"
            onClick={() => setShowBoxes((value) => !value)}
            className={classNames(
              "flex items-center gap-1.5 rounded-lg px-2 py-1 text-[10px] font-semibold uppercase tracking-wide transition",
              showBoxes
                ? "bg-[color:var(--accent-soft)] text-[color:var(--accent)]"
                : "bg-white/5 text-slate-500"
            )}
          >
            <ScanEye className="h-3.5 w-3.5" />
            {showBoxes ? "Boxes on" : "Boxes off"}
          </button>
        ) : (
          <span className="text-[10px] uppercase tracking-wide text-slate-600">
            {burnedInOverlays ? "Measured boxes recorded in clip" : "No detection overlay available"}
          </span>
        )}
      </div>

      {sourceLabel && (
        <p className="border-t border-[color:var(--glass-border)] bg-white/3 px-3 py-1.5 font-mono text-[10px] text-slate-600">
          {sourceLabel}
        </p>
      )}
    </div>
  );
};
