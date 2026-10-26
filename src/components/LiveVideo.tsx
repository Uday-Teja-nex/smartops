"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { fetchSourcePlayback } from "@/lib/api";

declare global {
  interface Window {
    MediaMTXWebRTCReader?: new (configuration: {
      url: string;
      onError: (error: string) => void;
      onTrack: (event: RTCTrackEvent) => void;
    }) => { close: () => void };
  }
}

export function LiveVideo({ sourceId }: { sourceId: string }) {
  const video = useRef<HTMLVideoElement>(null);
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState<string | null>("Connecting live video…");
  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    let reader: { close: () => void } | undefined;
    let previousTime = -1;
    let lastProgress = Date.now();
    const element = video.current;
    const timer = window.setInterval(() => {
      if (element && element.currentTime !== previousTime && element.readyState >= 2) {
        previousTime = element.currentTime;
        lastProgress = Date.now();
        setMessage(null);
      } else if (Date.now() - lastProgress > 4000) {
        setMessage((current) => current ?? "Live video stalled; reconnecting…");
      }
    }, 500);
    void fetchSourcePlayback(sourceId).then(({ whepUrl }) => {
      if (cancelled || !window.MediaMTXWebRTCReader) return;
      reader = new window.MediaMTXWebRTCReader({
        url: whepUrl,
        onError: () => { if (!cancelled) setMessage("Live video disconnected; retrying…"); },
        onTrack: (event) => {
          if (!cancelled && element) {
            element.srcObject = event.streams[0] ?? new MediaStream([event.track]);
            void element.play().catch(() => {
              if (!cancelled) setMessage("Select play to start live video");
            });
          }
        },
      });
    }).catch(() => {
      if (!cancelled) setMessage("Live video unavailable. Check the source relay and connection.");
    });
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      reader?.close();
      if (element) element.srcObject = null;
    };
  }, [sourceId, ready]);
  return <>
    <Script id={`mediamtx-reader-${sourceId}`} src="/vendor/mediamtx/reader.js"
      onLoad={() => setReady(true)} onReady={() => setReady(true)}
      onError={() => setMessage("Live player could not load")} />
    <video ref={video} autoPlay muted playsInline controls aria-label="Live camera video"
      className="absolute inset-0 h-full w-full object-contain" />
    {message && <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-slate-950/90 p-6 text-center text-sm text-slate-300">
      {message === "Select play to start live video" ? <button type="button"
        className="pointer-events-auto rounded border border-slate-500 px-4 py-2"
        onClick={() => { void video.current?.play().catch(() => setMessage("Select play to start live video")); }}>
        Play live video
      </button> : message}
    </div>}
  </>;
}
