from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

import cv2

from app.adapters.base import CandidateWindow, HealthResult, SourceAdapter

DEFAULT_WINDOW_SECONDS = 30.0
MAX_WINDOWS_PER_SOURCE = int(os.getenv("SMARTOPS_MAX_WINDOWS_PER_SOURCE", "12"))


class Mp4FileAdapter(SourceAdapter):
    """Fully supported local-development adapter for MP4 files."""

    adapter_name = "mp4-file"

    def _path(self) -> Path:
        return Path(str(self.source.get("sourceUri", "")))

    def probe(self) -> HealthResult:
        started = time.perf_counter()
        path = self._path()
        if not path.exists() or not path.is_file():
            return HealthResult(
                ok=False, status="failing", error=f"file not found: {path.name or path}"
            )

        capture = cv2.VideoCapture(str(path))
        try:
            if not capture.isOpened():
                return HealthResult(
                    ok=False, status="failing", error=f"unreadable video: {path.name}"
                )
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
            if frame_count <= 0:
                return HealthResult(
                    ok=False, status="failing", error=f"no readable frames: {path.name}"
                )
            duration = frame_count / fps if fps > 0 else 0.0
            return HealthResult(
                ok=True,
                status="online",
                latency_ms=(time.perf_counter() - started) * 1000,
                details={
                    "durationSeconds": round(duration, 2),
                    "fps": round(fps, 2),
                    "frameCount": frame_count,
                },
            )
        finally:
            capture.release()

    def discover_candidates(self) -> list[CandidateWindow]:
        path = self._path()
        stat = path.stat()
        content_key = f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}"

        capture = cv2.VideoCapture(str(path))
        try:
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        finally:
            capture.release()
        duration = frame_count / fps if fps > 0 else 0.0
        if duration <= 0:
            return []

        config = self.source.get("detectionConfig") or {}
        window_seconds = float(config.get("windowSeconds") or DEFAULT_WINDOW_SECONDS)
        window_seconds = max(5.0, window_seconds)

        windows: list[CandidateWindow] = []
        index = 0
        cursor = 0.0
        while cursor < duration and index < MAX_WINDOWS_PER_SOURCE:
            end = min(cursor + window_seconds, duration)
            raw = f"{content_key}:w{index}:{cursor:.1f}-{end:.1f}"
            signature = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
            windows.append(
                CandidateWindow(
                    window_index=index,
                    start_seconds=round(cursor, 2),
                    end_seconds=round(end, 2),
                    signature=signature,
                    details={"durationSeconds": round(duration, 2)},
                )
            )
            cursor = end
            index += 1
        return windows
