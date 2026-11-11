"""Demo history snapshot: `python -m app.demo_history export|clear`.

`demo.ps1 build-history` replays the recorded footage through the real
pipeline (incidents marked `detectionSummary.historyReplay`). `export` then
copies those incidents, their timeline and their evidence rows into a
manifest, and their evidence objects under the `history/` prefix of the
evidence bucket, which `reset_demo` keeps. Every reset re-imports the
snapshot after seeding, with all times shifted so the history ends at the
moment of the reset: the workspaces always show the last few days.
"""
from __future__ import annotations

import io
import json
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import DateTime, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import EvidenceItemModel, IncidentEventModel, IncidentModel, SourceModel

PREFIX = "history/"
MANIFEST_KEY = PREFIX + "manifest.json"
VERSION = 1
TABLES = (IncidentModel, IncidentEventModel, EvidenceItemModel)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _row(model, row) -> dict[str, Any]:
    out = {}
    for column in model.__table__.columns:
        value = getattr(row, column.key)
        out[column.key] = _aware(value).isoformat() if isinstance(value, datetime) else value
    return out


def _restore(model, data: dict[str, Any], shift: timedelta):
    values = {}
    for column in model.__table__.columns:
        value = data.get(column.key)
        if value is not None and isinstance(column.type, DateTime):
            value = datetime.fromisoformat(value) + shift
        values[column.key] = value
    return model(**values)


def is_replayed(incident: IncidentModel) -> bool:
    return bool((incident.detection_summary or {}).get("historyReplay"))


def build_manifest(session: Session, anchor: datetime) -> dict[str, Any]:
    incidents = [incident for incident in session.scalars(select(IncidentModel)).all() if is_replayed(incident)]
    ids = {incident.id for incident in incidents}
    events = [event for event in session.scalars(select(IncidentEventModel)).all() if event.incident_id in ids]
    evidence = [item for item in session.scalars(select(EvidenceItemModel)).all() if item.incident_id in ids]
    return {
        "version": VERSION,
        "anchor": anchor.isoformat(),
        "incidents": [_row(IncidentModel, row) for row in incidents],
        "events": [_row(IncidentEventModel, row) for row in events],
        "evidence": [_row(EvidenceItemModel, row) for row in evidence],
    }


def history_key(object_key: str) -> str:
    return object_key if object_key.startswith(PREFIX) else PREFIX + object_key


def import_manifest(session: Session, manifest: dict[str, Any], now: datetime | None = None) -> int:
    """Insert a snapshot, shifted so its anchor lands on `now`. Rows whose
    camera no longer exists in the seed are skipped."""
    if manifest.get("version") != VERSION:
        raise ValueError(f"Unsupported demo history version {manifest.get('version')!r}")
    now = now or datetime.now(UTC)
    shift = now - datetime.fromisoformat(manifest["anchor"])
    sources = set(session.scalars(select(SourceModel.id)).all())
    kept = {row["id"] for row in manifest["incidents"] if row["source_id"] in sources}
    for row in manifest["incidents"]:
        if row["id"] in kept:
            session.add(_restore(IncidentModel, row, shift))
    session.flush()
    for row in manifest["events"]:
        if row["incident_id"] in kept:
            session.add(_restore(IncidentEventModel, row, shift))
    for row in manifest["evidence"]:
        if row["incident_id"] in kept:
            session.add(_restore(EvidenceItemModel, {**row, "object_key": history_key(row["object_key"])}, shift))
    session.commit()
    return len(kept)


def import_history(session: Session) -> int:
    """Called by reset_demo after seeding; 0 when no snapshot was built."""
    from app.config import get_settings
    from app.storage import internal_client

    settings = get_settings()
    if not settings.evidence_storage_enabled:
        return 0
    client = internal_client()
    try:
        response = client.get_object(settings.minio_bucket, MANIFEST_KEY)
    except Exception:  # noqa: BLE001 - no snapshot yet (S3Error NoSuchKey)
        return 0
    try:
        manifest = json.loads(response.read())
    finally:
        response.close()
        response.release_conn()
    return import_manifest(session, manifest)


def export() -> int:
    from minio.commonconfig import CopySource

    from app.config import get_settings
    from app.storage import ensure_bucket, internal_client

    settings = get_settings()
    if not settings.evidence_storage_enabled:
        print("Evidence storage is disabled; nothing to export", file=sys.stderr)
        return 1
    ensure_bucket()
    client = internal_client()
    with SessionLocal() as session:
        manifest = build_manifest(session, datetime.now(UTC))
    if not manifest["incidents"]:
        print("No replayed incidents found; run the history replay first", file=sys.stderr)
        return 1
    for row in manifest["evidence"]:
        target = history_key(row["object_key"])
        if target != row["object_key"]:
            client.copy_object(settings.minio_bucket, target, CopySource(settings.minio_bucket, row["object_key"]))
        row["object_key"] = target
    data = json.dumps(manifest).encode("utf-8")
    client.put_object(settings.minio_bucket, MANIFEST_KEY, io.BytesIO(data), len(data),
                      content_type="application/json")
    print(f"Demo history exported: {len(manifest['incidents'])} incidents, {len(manifest['events'])} timeline "
          f"events, {len(manifest['evidence'])} evidence items")
    return 0


def clear() -> int:
    """Delete the snapshot (manifest and objects) before building a new one."""
    from minio.deleteobjects import DeleteObject

    from app.config import get_settings
    from app.storage import ensure_bucket, internal_client

    settings = get_settings()
    if not settings.evidence_storage_enabled:
        return 0
    ensure_bucket()
    client = internal_client()
    objects = [DeleteObject(item.object_name)
               for item in client.list_objects(settings.minio_bucket, prefix=PREFIX, recursive=True)]
    errors = list(client.remove_objects(settings.minio_bucket, objects)) if objects else []
    if errors:
        print(f"Could not delete {len(errors)} history objects", file=sys.stderr)
        return 1
    print(f"Demo history snapshot cleared ({len(objects)} objects)")
    return 0


if __name__ == "__main__":
    commands = {"export": export, "clear": clear}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        print("usage: python -m app.demo_history export|clear", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(commands[sys.argv[1]]())
