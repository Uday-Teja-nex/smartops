"""Demo history: replayed incidents are stamped in the past, marked, silent,
and survive reset through a time-shifted snapshot."""
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

REPLAY = {"historyReplay": {"builtAt": "2026-11-11T12:00:00Z", "clip": "mall-atrium"}}


@pytest.fixture(scope="module")
def history_source(client, service_headers):
    response = client.post("/v1/sources", headers=service_headers, json={
        "name": "History Cam", "buildingId": "bldg-north-01", "floor": "L1", "zone": "Lobby Atrium",
        "sourceType": "file", "sourceUri": "/app/sample-data/input/history.mp4"})
    assert response.status_code == 201, response.text
    return response.json()


def _payload(source_id, **overrides):
    payload = {
        "category": "Security", "subcategory": "crowding", "type": "crowding", "severity": "medium",
        "confidence": 0.9, "buildingId": "bldg-north-01", "floor": "L1", "zone": "Lobby Atrium",
        "sourceId": source_id, "startTime": "2026-11-09T10:00:00Z", "shortSummary": "6 people in Lobby Atrium",
        "evidence": {"thumbnailUrl": "", "clipUrl": "", "restricted": True},
        "modelProvider": "rule-engine", "modelVersion": "zone-rules-v1",
        "detectionSummary": {"count": 6, **REPLAY}, "replay": True,
    }
    payload.update(overrides)
    return payload


def _events(incident_id):
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import IncidentEventModel

    with SessionLocal() as session:
        return session.scalars(select(IncidentEventModel).where(IncidentEventModel.incident_id == incident_id)
                               .order_by(IncidentEventModel.created_at)).all()


def _at(value):
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def test_replayed_incident_is_stamped_at_its_time_and_never_notifies(client, history_source, service_headers,
                                                                     monkeypatch):
    from app.routers import incidents

    enqueue, publish = Mock(), Mock()
    monkeypatch.setattr(incidents, "enqueue_for_incident", enqueue)
    monkeypatch.setattr(incidents, "publish_event", publish)
    response = client.post("/v1/incidents", headers=service_headers,
                           json=_payload(history_source["id"], id="inc-history-1"))
    assert response.status_code == 201, response.text
    enqueue.assert_not_called()
    publish.assert_not_called()
    [created] = _events("inc-history-1")
    assert _at(created.created_at) == datetime(2026, 11, 9, 10, tzinfo=UTC)
    assert created.actor == "history replay" and "recorded footage replayed" in created.note

    # The evidence update is replayed too: same time, still silent.
    update = client.post("/v1/incidents", headers=service_headers, json=_payload(
        history_source["id"], id="inc-history-1", evidence={"thumbnailUrl": "/v1/evidence/x/url",
                                                          "clipUrl": "/v1/evidence/y/url", "restricted": True}))
    assert update.status_code == 201, update.text
    publish.assert_not_called()


def test_only_the_pipeline_replays_and_only_marked_incidents(client, history_source, service_headers,
                                                             supervisor_headers):
    body = _payload(history_source["id"], id="inc-history-2")
    assert client.post("/v1/incidents", headers=supervisor_headers, json=body).status_code == 403
    unmarked = _payload(history_source["id"], id="inc-history-3", detectionSummary={"count": 6})
    assert client.post("/v1/incidents", headers=service_headers, json=unmarked).status_code == 422
    live = _payload(history_source["id"], id="inc-live-1", replay=False, detectionSummary={"count": 6})
    assert client.post("/v1/incidents", headers=service_headers, json=live).status_code == 201
    # A live incident can never be rewritten as replayed history.
    again = _payload(history_source["id"], id="inc-live-1")
    assert client.post("/v1/incidents", headers=service_headers, json=again).status_code == 409


def test_scripted_actions_are_labelled_and_limited_to_history(client, history_source, service_headers,
                                                              supervisor_headers):
    client.post("/v1/incidents", headers=service_headers, json=_payload(history_source["id"], id="inc-history-4"))
    at = "2026-11-09T10:03:00Z"
    response = client.post("/v1/incidents/inc-history-4/replay-action", headers=service_headers,
                           json={"action": "acknowledge", "at": at})
    assert response.status_code == 200, response.text
    resolved = client.post("/v1/incidents/inc-history-4/replay-action", headers=service_headers,
                           json={"action": "resolve", "at": "2026-11-09T10:12:00Z"})
    assert resolved.json()["status"] == "resolved"
    actions = [event for event in _events("inc-history-4") if event.action in {"acknowledge", "resolve"}]
    assert [event.actor for event in actions] == ["Scripted demo action"] * 2
    assert all("not a real operator" in event.note for event in actions)
    assert _at(actions[0].created_at) == datetime(2026, 11, 9, 10, 3, tzinfo=UTC)

    early = {"action": "resolve", "at": "2026-11-09T09:00:00Z"}
    assert client.post("/v1/incidents/inc-history-4/replay-action", headers=service_headers,
                       json=early).status_code == 422
    assert client.post("/v1/incidents/inc-history-4/replay-action", headers=supervisor_headers,
                       json={"action": "resolve", "at": at}).status_code == 403
    client.post("/v1/incidents", headers=service_headers,
                json=_payload(history_source["id"], id="inc-live-2", replay=False, detectionSummary={}))
    assert client.post("/v1/incidents/inc-live-2/replay-action", headers=service_headers,
                       json={"action": "resolve", "at": at}).status_code == 409


def test_snapshot_round_trip_shifts_history_to_end_now(client, history_source, service_headers):
    from sqlalchemy import delete, select

    from app.db import SessionLocal
    from app.demo_history import build_manifest, import_manifest
    from app.models import EvidenceItemModel, IncidentEventModel, IncidentModel

    client.post("/v1/incidents", headers=service_headers, json=_payload(history_source["id"], id="inc-history-5"))
    client.post("/v1/evidence", headers=service_headers, json={
        "sourceId": history_source["id"], "incidentId": "inc-history-5", "kind": "clip",
        "objectKey": "streams/x/inc-history-5/clip.mp4", "contentType": "video/mp4", "sizeBytes": 10,
        "restricted": True, "meta": {}})
    anchor = datetime(2026, 11, 11, 12, tzinfo=UTC)
    with SessionLocal() as session:
        manifest = build_manifest(session, anchor)
        ids = [row["id"] for row in manifest["incidents"]]
        assert "inc-history-5" in ids and "inc-live-1" not in ids
        # Simulate reset: remove the history rows, then import a week later.
        session.execute(delete(EvidenceItemModel).where(EvidenceItemModel.incident_id.in_(ids)))
        session.execute(delete(IncidentEventModel).where(IncidentEventModel.incident_id.in_(ids)))
        session.execute(delete(IncidentModel).where(IncidentModel.id.in_(ids)))
        session.commit()
        restored = import_manifest(session, manifest, now=anchor + timedelta(days=7))
        assert restored == len(ids)
        incident = session.get(IncidentModel, "inc-history-5")
        assert _at(incident.start_time) == datetime(2026, 11, 16, 10, tzinfo=UTC)
        [clip] = session.scalars(select(EvidenceItemModel).where(EvidenceItemModel.incident_id == "inc-history-5"))
        assert clip.object_key == "history/streams/x/inc-history-5/clip.mp4"


def test_retention_never_deletes_the_history_snapshot_objects(monkeypatch):
    from app import config, retention, storage

    removed = Mock()
    monkeypatch.setattr(config, "get_settings", lambda: Mock(evidence_storage_enabled=True, minio_bucket="b"))
    monkeypatch.setattr(storage, "internal_client", lambda: Mock(remove_object=removed))
    retention.remove_from_storage("history/streams/x/clip.mp4")
    removed.assert_not_called()
    retention.remove_from_storage("streams/x/clip.mp4")
    removed.assert_called_once()
