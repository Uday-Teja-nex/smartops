"""Evidence older than the workspace retention period is purged, and the timeline says so."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import EvidenceAccessModel, EvidenceItemModel, IncidentEventModel, OrganizationModel
from app.retention import purge_expired_evidence, retention_days


def test_old_evidence_is_purged_with_an_audit_note(client, service_headers):
    source = client.post('/v1/sources', headers=service_headers, json={
        'name': 'Retention cam', 'buildingId': 'bldg-north-01', 'floor': 'L1', 'zone': 'Lobby Atrium',
        'sourceType': 'rtsp', 'sourceUri': 'rtsp://mediamtx:8554/retention'}).json()
    incident = client.post('/v1/incidents', headers=service_headers, json={
        'category': 'Security', 'type': 'restricted_entry', 'severity': 'high', 'confidence': 1,
        'buildingId': 'bldg-north-01', 'floor': 'L1', 'zone': 'Lab', 'sourceId': source['id'],
        'startTime': '2026-01-01T00:00:00Z', 'shortSummary': 'x',
        'evidence': {'thumbnailUrl': '', 'clipUrl': '', 'restricted': True}}).json()
    now = datetime.now(UTC)
    with Session(engine) as session:
        for key, age in (('old-clip', 45), ('new-clip', 2)):
            session.add(EvidenceItemModel(id=f'evd-{key}', org_id='org-demo', incident_id=incident['id'],
                                          source_id=source['id'], kind='clip', object_key=f'{key}.mp4',
                                          content_type='video/mp4', restricted=True, meta={},
                                          created_at=now - timedelta(days=age)))
        session.flush()
        session.add(EvidenceAccessModel(id='eva-old', org_id='org-demo', evidence_id='evd-old-clip',
                                        actor_id='usr-admin', actor_role='admin', created_at=now))
        session.commit()
        removed = []
        assert purge_expired_evidence(session, removed.append, now=now) >= 1
        assert 'old-clip.mp4' in removed and 'new-clip.mp4' not in removed
        assert session.get(EvidenceItemModel, 'evd-old-clip') is None
        assert session.get(EvidenceItemModel, 'evd-new-clip') is not None
        assert session.get(EvidenceAccessModel, 'eva-old') is None
        notes = session.scalars(select(IncidentEventModel.note).where(
            IncidentEventModel.incident_id == incident['id'], IncidentEventModel.action == 'evidence_purged')).all()
        assert notes == ['1 evidence item(s) older than 30 days deleted under the workspace retention policy']


def test_failed_object_removal_keeps_rows_for_the_next_run():
    import pytest
    with Session(engine) as session:
        session.add(EvidenceItemModel(id='evd-stuck', org_id='org-demo', source_id='src-office-lobby', kind='clip',
                                      object_key='stuck.mp4', content_type='video/mp4', restricted=True, meta={},
                                      created_at=datetime.now(UTC) - timedelta(days=90)))
        session.commit()
        def boom(key):
            raise OSError('storage down')
        with pytest.raises(OSError):
            purge_expired_evidence(session, boom)
        session.rollback()
        assert session.get(EvidenceItemModel, 'evd-stuck') is not None
        session.delete(session.get(EvidenceItemModel, 'evd-stuck'))
        session.commit()


def test_retention_setting_is_admin_only_and_validated(client, admin_headers, supervisor_headers):
    assert client.put('/v1/org/settings', headers=supervisor_headers,
                      json={'settings': {'evidenceRetentionDays': 7}}).status_code == 403
    assert client.put('/v1/org/settings', headers=admin_headers,
                      json={'settings': {'evidenceRetentionDays': 0}}).status_code == 422
    assert client.put('/v1/org/settings', headers=admin_headers,
                      json={'settings': {'evidenceRetentionDays': 14}}).status_code == 200
    with Session(engine) as session:
        assert retention_days(session.get(OrganizationModel, 'org-demo')) == 14
    client.put('/v1/org/settings', headers=admin_headers, json={'settings': {'evidenceRetentionDays': 30}})
