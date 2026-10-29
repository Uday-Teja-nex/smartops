"""Bounded RTSP capture shared by live cameras and looped recordings."""
from __future__ import annotations

import time
import os
from dataclasses import dataclass
from threading import Event, Lock, Thread

import cv2
import numpy as np

from app.adapters.base import CandidateWindow, HealthResult, SourceAdapter


def open_capture(uri: str):
    threads = int(os.getenv('SMARTOPS_RTSP_DECODE_THREADS', '1'))
    if not 1 <= threads <= 16:
        raise ValueError('SMARTOPS_RTSP_DECODE_THREADS must be between 1 and 16')
    # FFmpeg open/read timeouts are constructor parameters, not later setters.
    return cv2.VideoCapture(uri, cv2.CAP_FFMPEG, [
        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
        cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000,
        cv2.CAP_PROP_N_THREADS, threads,
    ])


@dataclass(frozen=True)
class StreamFrame:
    image: np.ndarray
    sequence: int
    captured_at: float
    monotonic_at: float


class StreamReader:
    """Drain frames continuously with one retained frame, preventing stale backlog.

    Consumers check monotonic_at for freshness. Reconnects never refresh the
    timestamp of an old frame. Each reader owns its decoder on one thread.
    """

    def __init__(self, uri: str, *, stop: Event | None = None,
                 capture_factory=None, retry_initial=0.5, retry_max=8.0):
        self.uri = uri
        self.stop = stop if stop is not None else Event()
        self.capture_factory = capture_factory or open_capture
        self.retry_initial = retry_initial
        self.retry_max = retry_max
        self.sequence = 0
        self.last_error: str | None = "Waiting for first frame"
        self._frame: StreamFrame | None = None
        self._lock = Lock()
        self._thread: Thread | None = None

    def latest(self) -> StreamFrame | None:
        with self._lock:
            return self._frame

    def start(self):
        if self._thread is not None:
            raise RuntimeError("Reader already started")
        self._thread = Thread(target=self.run, daemon=True, name="rtsp-reader")
        self._thread.start()
        return self

    def close(self):
        self.stop.set()
        if self._thread:
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                raise RuntimeError("RTSP reader did not stop within timeout")

    def run(self):
        delay = self.retry_initial
        while not self.stop.is_set():
            capture = None
            try:
                capture = self.capture_factory(self.uri)
                if not capture.isOpened():
                    self.last_error = "RTSP connection unavailable"
                else:
                    while not self.stop.is_set():
                        ok, image = capture.read()
                        if not ok or image is None:
                            self.last_error = "RTSP frame read failed"
                            break
                        self.sequence += 1
                        frame = StreamFrame(image, self.sequence, time.time(), time.monotonic())
                        with self._lock:
                            self._frame = frame
                        self.last_error = None
                        delay = self.retry_initial
            except Exception as exc:
                # Exception messages can contain source credentials.
                self.last_error = f"RTSP capture failed ({type(exc).__name__})"
            finally:
                if capture is not None:
                    capture.release()
            if self.stop.wait(delay):
                break
            delay = min(self.retry_max, max(self.retry_initial, delay * 2))


class RtspAdapter(SourceAdapter):
    adapter_name = "rtsp"

    def probe(self) -> HealthResult:
        started = time.monotonic()
        capture = None
        try:
            capture = open_capture(self.source["sourceUri"])
            ok, frame = capture.read() if capture.isOpened() else (False, None)
            if ok and frame is not None:
                return HealthResult(True, "online", (time.monotonic() - started) * 1000,
                                    adapter=self.adapter_name)
            return HealthResult(False, "offline", error="RTSP frame unavailable", adapter=self.adapter_name)
        except Exception as exc:
            return HealthResult(False, "offline", error=f"RTSP probe failed ({type(exc).__name__})",
                                adapter=self.adapter_name)
        finally:
            if capture is not None:
                capture.release()

    def discover_candidates(self) -> list[CandidateWindow]:
        # Live sources belong to continuous processing, never file windows.
        return []

    def reader(self) -> StreamReader:
        return StreamReader(self.source["sourceUri"])
