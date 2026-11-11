"""Evidence retention: purge clips and snapshots older than each workspace's limit.

Workspace setting `evidenceRetentionDays` (default 30, 1-3650). Objects are
removed from object storage first, then their rows (and access-audit rows);
each affected incident's timeline records the purge so the history explains
why evidence is gone. Incidents themselves are kept.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Callable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import EvidenceAccessModel, EvidenceItemModel, IncidentModel, OrganizationModel

DEFAULT_RETENTION_DAYS = 30


def retention_days(org: OrganizationModel) -> int:
    value = (org.settings or {}).get("evidenceRetentionDays", DEFAULT_RETENTION_DAYS)
    try:
        days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_RETENTION_DAYS
    return min(max(days, 1), 3650)


def purge_expired_evidence(session: Session, remove_object: Callable[[str], None],
                           now: datetime | None = None) -> int:
    from app.routers.incidents import record_incident_event

    now = now or datetime.now(UTC)
    purged = 0
    for org in session.scalars(select(OrganizationModel)).all():
        days = retention_days(org)
        cutoff = now - timedelta(days=days)
        items = session.scalars(select(EvidenceItemModel).where(
            EvidenceItemModel.org_id == org.id, EvidenceItemModel.created_at < cutoff)).all()
        by_incident: dict[str, int] = defaultdict(int)
        for item in items:
            remove_object(item.object_key)  # raise on failure: rows stay, retried next run
            session.execute(delete(EvidenceAccessModel).where(EvidenceAccessModel.evidence_id == item.id))
            if item.incident_id:
                by_incident[item.incident_id] += 1
            session.delete(item)
            purged += 1
        for incident_id, count in by_incident.items():
            incident = session.get(IncidentModel, incident_id)
            if incident is not None:
                record_incident_event(session, incident, actor="retention policy", action="evidence_purged",
                                      note=f"{count} evidence item(s) older than {days} days deleted "
                                           "under the workspace retention policy")
        session.commit()
    return purged


def remove_from_storage(object_key: str) -> None:
    from app.config import get_settings
    from app.storage import internal_client

    from app.demo_history import PREFIX

    settings = get_settings()
    # Demo history objects back the snapshot every reset restores from; the
    # expired rows go, the snapshot's copy stays.
    if settings.evidence_storage_enabled and not object_key.startswith(PREFIX):
        internal_client().remove_object(settings.minio_bucket, object_key)
