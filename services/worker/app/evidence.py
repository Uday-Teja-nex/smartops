"""Evidence generation and upload for candidate windows.

Produces three artifacts per incident and stores them in MinIO/S3:
  - snapshot.jpg   (middle sampled frame, full worker resolution)
  - thumbnail.jpg  (320px-wide resize of the snapshot)
  - clip.mp4       (ffmpeg trim of the candidate window, capped length)

If object storage or ffmpeg is unavailable the pipeline degrades honestly:
the incident keeps its restricted placeholder evidence and a note is logged.
"""

from __future__ import annotations

import base64
import io
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import cv2
import httpx
import numpy as np
from minio import Minio

from app.log import log

MINIO_ENDPOINT = os.getenv("SMARTOPS_MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("SMARTOPS_MINIO_ACCESS_KEY", "smartops")
MINIO_SECRET_KEY = os.getenv("SMARTOPS_MINIO_SECRET_KEY", "smartopsminio")
MINIO_BUCKET = os.getenv("SMARTOPS_MINIO_BUCKET", "smartops-evidence")
EVIDENCE_ENABLED = os.getenv("SMARTOPS_EVIDENCE_ENABLED", "true").lower() in {"1", "true", "yes"}
CLIP_MAX_SECONDS = float(os.getenv("SMARTOPS_EVIDENCE_CLIP_MAX_SECONDS", "20"))
THUMBNAIL_WIDTH = 320

_client: Minio | None = None


def _minio() -> Minio:
    global _client
    if _client is None:
        parsed = urlparse(MINIO_ENDPOINT)
        _client = Minio(
            parsed.netloc or parsed.path,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=parsed.scheme == "https",
        )
        if not _client.bucket_exists(MINIO_BUCKET):
            _client.make_bucket(MINIO_BUCKET)
    return _client


def _put_bytes(object_key: str, data: bytes, content_type: str) -> None:
    _minio().put_object(
        MINIO_BUCKET,
        object_key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def _make_thumbnail(snapshot_bytes: bytes) -> tuple[bytes, int, int] | None:
    image = cv2.imdecode(np.frombuffer(snapshot_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return None
    height, width = image.shape[:2]
    scale = THUMBNAIL_WIDTH / max(width, 1)
    thumb = cv2.resize(
        image, (THUMBNAIL_WIDTH, max(1, int(height * scale))), interpolation=cv2.INTER_AREA
    )
    ok, encoded = cv2.imencode(".jpg", thumb, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        return None
    return encoded.tobytes(), thumb.shape[1], thumb.shape[0]


def _make_clip(source_path: Path, window_start: float, window_end: float) -> bytes | None:
    duration = min(max(window_end - window_start, 1.0), CLIP_MAX_SECONDS)
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "clip.mp4"
        command = [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-ss",
            f"{max(window_start, 0):.2f}",
            "-i",
            str(source_path),
            "-t",
            f"{duration:.2f}",
            "-vf",
            "scale=640:-2",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-an",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        try:
            subprocess.run(command, check=True, timeout=120)
        except (subprocess.SubprocessError, FileNotFoundError) as exc:
            log("clip_generation_failed", level="warning", error=str(exc))
            return None
        if not out_path.exists() or out_path.stat().st_size == 0:
            return None
        return out_path.read_bytes()


def _register_evidence(
    client: httpx.Client,
    api_base_url: str,
    *,
    source_id: str,
    candidate_id: str,
    kind: str,
    object_key: str,
    content_type: str,
    width: int | None = None,
    height: int | None = None,
    duration_seconds: float | None = None,
    size_bytes: int | None = None,
    meta: dict[str, Any] | None = None,
) -> str | None:
    response = client.post(
        f"{api_base_url}/v1/evidence",
        json={
            "sourceId": source_id,
            "candidateId": candidate_id,
            "kind": kind,
            "objectKey": object_key,
            "contentType": content_type,
            "width": width,
            "height": height,
            "durationSeconds": duration_seconds,
            "sizeBytes": size_bytes,
            "restricted": True,
            "meta": meta or {},
        },
    )
    if not response.is_success:
        log(
            "evidence_register_failed",
            level="warning",
            kind=kind,
            statusCode=response.status_code,
        )
        return None
    return response.json()["id"]


def generate_and_store_evidence(
    client: httpx.Client,
    api_base_url: str,
    job: dict[str, Any],
    frames: list[dict[str, Any]],
    source_path: Path,
) -> dict[str, str]:
    """Returns evidence URL overrides for the incident draft (may be empty)."""
    if not EVIDENCE_ENABLED or not frames:
        return {}

    source = job.get("source") or job.get("camera") or {}
    source_id = str(source.get("id"))
    candidate_id = str(job["candidateId"])
    prefix = f"{source_id}/{candidate_id}"
    overrides: dict[str, str] = {}

    try:
        snapshot = frames[len(frames) // 2]
        snapshot_bytes = base64.b64decode(snapshot["imageBase64"])

        _put_bytes(f"{prefix}/snapshot.jpg", snapshot_bytes, "image/jpeg")
        _register_evidence(
            client,
            api_base_url,
            source_id=source_id,
            candidate_id=candidate_id,
            kind="snapshot",
            object_key=f"{prefix}/snapshot.jpg",
            content_type="image/jpeg",
            size_bytes=len(snapshot_bytes),
            meta={"timestampSeconds": snapshot.get("timestampSeconds")},
        )

        thumb = _make_thumbnail(snapshot_bytes)
        if thumb is not None:
            thumb_bytes, thumb_w, thumb_h = thumb
            _put_bytes(f"{prefix}/thumbnail.jpg", thumb_bytes, "image/jpeg")
            thumb_id = _register_evidence(
                client,
                api_base_url,
                source_id=source_id,
                candidate_id=candidate_id,
                kind="thumbnail",
                object_key=f"{prefix}/thumbnail.jpg",
                content_type="image/jpeg",
                width=thumb_w,
                height=thumb_h,
                size_bytes=len(thumb_bytes),
            )
            if thumb_id:
                overrides["thumbnailUrl"] = f"/v1/evidence/{thumb_id}/url"

        window_start = float(job.get("windowStart") or 0)
        window_end = float(job.get("windowEnd") or window_start + CLIP_MAX_SECONDS)
        clip_bytes = _make_clip(source_path, window_start, window_end)
        if clip_bytes is not None:
            _put_bytes(f"{prefix}/clip.mp4", clip_bytes, "video/mp4")
            clip_id = _register_evidence(
                client,
                api_base_url,
                source_id=source_id,
                candidate_id=candidate_id,
                kind="clip",
                object_key=f"{prefix}/clip.mp4",
                content_type="video/mp4",
                duration_seconds=min(window_end - window_start, CLIP_MAX_SECONDS),
                size_bytes=len(clip_bytes),
                meta={"windowStart": window_start, "windowEnd": window_end},
            )
            if clip_id:
                overrides["clipUrl"] = f"/v1/evidence/{clip_id}/url"

        log("evidence_stored", candidateId=candidate_id, artifacts=list(overrides.keys()) or ["snapshot"])
    except Exception as exc:  # noqa: BLE001 - evidence is best-effort, never fatal.
        log(
            "evidence_storage_failed",
            level="warning",
            candidateId=candidate_id,
            error=f"{exc.__class__.__name__}: {exc}",
        )
        return {}

    return overrides
