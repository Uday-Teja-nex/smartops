import pytest


@pytest.fixture(scope="module")
def pipeline_source(client, service_headers):
    """A source created by the service principal, as ingest would."""
    response = client.post(
        "/v1/sources",
        headers=service_headers,
        json={
            "name": "Pipeline Cam",
            "buildingId": "bldg-north-01",
            "floor": "L1",
            "zone": "Lobby Atrium",
            "sourceType": "file",
            "sourceUri": "/app/sample-data/input/pipeline.mp4",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _incident_payload(source_id: str, **overrides):
    payload = {
        "category": "Safety",
        "subcategory": "blocked_exit",
        "type": "exit_blocked",
        "severity": "critical",
        "confidence": 0.91,
        "buildingId": "bldg-north-01",
        "floor": "L1",
        "zone": "Lobby Atrium",
        "sourceId": source_id,
        "candidateId": "cand-test-1",
        "startTime": "2026-07-07T10:00:00Z",
        "shortSummary": "Exit blocked by pallet",
        "detailedNarrative": ["A pallet blocks the egress door."],
        "recommendedActions": ["Remove the pallet."],
        "evidence": {"thumbnailUrl": "/t", "clipUrl": "/c", "restricted": True},
        "modelProvider": "ollama",
        "modelVersion": "qwen2.5vl:3b/llama3.2:3b",
        "detectionSummary": {"labels": {"person": 2}, "detectorStatus": "ran"},
    }
    payload.update(overrides)
    return payload


def test_incident_cannot_claim_a_different_building(client, pipeline_source, service_headers):
    response = client.post('/v1/incidents', headers=service_headers,
                           json=_incident_payload(pipeline_source['id'], buildingId='foreign-building'))
    assert response.status_code == 422


def test_evidence_links_must_match_incident_source_and_candidate(client, pipeline_source, service_headers):
    incident = client.post('/v1/incidents', headers=service_headers,
                           json=_incident_payload(pipeline_source['id'], candidateId='cand-evidence-links')).json()
    other = client.post('/v1/sources', headers=service_headers, json={
        'name': 'Other evidence camera', 'buildingId': 'bldg-north-01',
        'floor': 'L1', 'zone': 'Lobby Atrium', 'sourceType': 'file',
        'sourceUri': '/app/sample-data/input/other.mp4',
    }).json()
    payload = {'sourceId': other['id'], 'incidentId': incident['id'],
               'candidateId': 'cand-evidence-links', 'kind': 'snapshot',
               'objectKey': 'tests/evidence.jpg', 'contentType': 'image/jpeg'}
    assert client.post('/v1/evidence', headers=service_headers, json=payload).status_code == 422
    payload['sourceId'] = pipeline_source['id']
    payload['candidateId'] = 'wrong-candidate'
    assert client.post('/v1/evidence', headers=service_headers, json=payload).status_code == 422
    payload['candidateId'] = 'cand-evidence-links'
    saved = client.post('/v1/evidence', headers=service_headers, json=payload)
    assert saved.status_code == 201
    # Candidate IDs alone must not join evidence from another camera.
    foreign = client.post('/v1/evidence', headers=service_headers,
                          json={**payload, 'sourceId': other['id'], 'incidentId': None})
    assert foreign.status_code == 201
    listed = client.get('/v1/evidence', headers=service_headers,
                        params={'incidentId': incident['id']}).json()
    assert {item['id'] for item in listed} == {saved.json()['id']}
    detail = client.get('/v1/incidents/' + incident['id'], headers=service_headers).json()
    assert {item['id'] for item in detail['evidenceItems']} == {saved.json()['id']}


def test_full_incident_lifecycle_with_audit(
    client, pipeline_source, service_headers, operator_headers, viewer_headers
):
    created = client.post(
        "/v1/incidents", headers=service_headers, json=_incident_payload(pipeline_source["id"])
    )
    assert created.status_code == 201, created.text
    incident = created.json()
    incident_id = incident["id"]
    assert incident["status"] == "active"
    assert incident["slaDueAt"] is not None
    assert incident["subcategory"] == "blocked_exit"
    assert "cameraId" not in incident
    assert incident["sourceId"] == pipeline_source["id"]
    # Legacy URLs must not bypass per-object authorization and issuance audit.
    assert incident['evidence']['clipUrl'] == ''
    assert incident['evidence']['thumbnailUrl'] == ''

    # viewer: read yes, mutate no
    assert client.get(f"/v1/incidents/{incident_id}", headers=viewer_headers).status_code == 200
    assert (
        client.patch(f"/v1/incidents/{incident_id}/resolve", headers=viewer_headers).status_code
        == 403
    )

    acked = client.patch(f"/v1/incidents/{incident_id}/acknowledge", headers=operator_headers)
    assert acked.json()["status"] == "acknowledged"
    assert acked.json()["ackTime"] is not None

    assigned = client.patch(
        f"/v1/incidents/{incident_id}/assign",
        headers=operator_headers,
        json={"assignee": "Response Team A"},
    )
    assert assigned.json()["status"] == "assigned"
    assert assigned.json()["assignedTo"] == "Response Team A"

    in_progress = client.patch(
        f"/v1/incidents/{incident_id}/status",
        headers=operator_headers,
        json={"status": "in_progress", "note": "On site now"},
    )
    assert in_progress.json()["status"] == "in_progress"

    escalated = client.patch(
        f"/v1/incidents/{incident_id}/status",
        headers=operator_headers,
        json={"status": "escalated"},
    )
    assert escalated.json()["status"] == "escalated"
    assert escalated.json()["escalatedAt"] is not None

    comment = client.post(
        f"/v1/incidents/{incident_id}/comments",
        headers=operator_headers,
        json={"body": "Blocked exit confirmed, clearing now."},
    )
    assert comment.status_code == 201

    resolved = client.patch(f"/v1/incidents/{incident_id}/resolve", headers=operator_headers)
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolvedTime"] is not None

    detail = client.get(f"/v1/incidents/{incident_id}", headers=viewer_headers).json()
    actions = [event["action"] for event in detail["events"]]
    assert actions == [
        "created",
        "acknowledge",
        "assign",
        "status_change",
        "status_change",
        "comment",
        "resolve",
    ]
    assert detail["comments"][0]["body"] == "Blocked exit confirmed, clearing now."
    actors = {event["actor"] for event in detail["events"]}
    assert "pipeline" in actors
    assert any("Olivia Operator" in actor for actor in actors)


def test_incident_upsert_is_idempotent_and_preserves_lifecycle(
    client, pipeline_source, service_headers, operator_headers
):
    payload = _incident_payload(pipeline_source["id"], id="inc-idempotent-1")
    first = client.post("/v1/incidents", headers=service_headers, json=payload)
    assert first.status_code == 201

    client.patch("/v1/incidents/inc-idempotent-1/acknowledge", headers=operator_headers)

    payload["shortSummary"] = "Updated summary from pipeline retry"
    second = client.post("/v1/incidents", headers=service_headers, json=payload)
    assert second.status_code == 201
    body = second.json()
    assert body["shortSummary"] == "Updated summary from pipeline retry"
    # Operator lifecycle state must survive pipeline re-submissions.
    assert body["status"] == "acknowledged"


def test_incident_requires_known_source(client, service_headers):
    response = client.post(
        "/v1/incidents", headers=service_headers, json=_incident_payload("src-missing")
    )
    assert response.status_code == 404


def test_report_counts_beyond_bootstrap_limit(client, pipeline_source, service_headers, viewer_headers):
    from datetime import UTC, datetime, timedelta
    from sqlalchemy import delete
    from app.db import SessionLocal
    from app.models import IncidentModel
    payload = _incident_payload(pipeline_source['id'], id='report-template', startTime='2025-01-01T12:00:00Z')
    assert client.post('/v1/incidents', headers=service_headers, json=payload).status_code == 201
    with SessionLocal() as session:
        template = session.get(IncidentModel, 'report-template')
        values = {column.name: getattr(template, column.name) for column in IncidentModel.__table__.columns}
        for index in range(201):
            started = datetime(2025, 1, 2, 12, tzinfo=UTC)
            session.add(IncidentModel(**(values | {
                'id': f'report-row-{index}', 'start_time': started,
                'ack_time': started + timedelta(minutes=10), 'status': 'false_positive',
            })))
        session.commit()
    try:
        params = {'start': '2025-01-02T00:00:00Z', 'end': '2025-01-03T00:00:00Z'}
        response = client.get('/v1/reports/summary', headers=viewer_headers, params=params)
        assert response.status_code == 200
        report = response.json()
        assert report['totalIncidents'] == 201
        assert report['averageAckMinutes'] == 10
        assert report['averageResolveMinutes'] is None
        assert report['falsePositiveRate'] == 1
        assert report['daily'] == [{'date': '2025-01-02', 'count': 201}]
        assert client.get('/v1/reports/summary', headers=viewer_headers,
                          params=params | {'buildingId': 'unknown'}).status_code == 404
        assert client.get('/v1/reports/summary', headers=viewer_headers,
                          params=params | {'end': '2026-01-03T00:00:00Z'}).status_code == 422
    finally:
        with SessionLocal() as session:
            session.execute(delete(IncidentModel).where(IncidentModel.id.like('report-row-%')))
            session.commit()


def test_replay_cannot_rebind_incident_identity(client, pipeline_source, service_headers):
    payload = _incident_payload(pipeline_source['id'], id='inc-identity-locked')
    first = client.post('/v1/incidents', headers=service_headers, json=payload)
    assert first.status_code == 201
    other = client.post('/v1/sources', headers=service_headers, json={
        'name': 'Replay camera', 'buildingId': 'bldg-north-01', 'floor': 'L1',
        'zone': 'Lobby Atrium', 'sourceType': 'file', 'sourceUri': '/app/sample-data/input/replay.mp4',
    }).json()
    for changes in ({'sourceId': other['id']}, {'candidateId': 'another-candidate'}):
        response = client.post('/v1/incidents', headers=service_headers, json={**payload, **changes})
        assert response.status_code == 409
    detail = client.get('/v1/incidents/' + payload['id'], headers=service_headers).json()
    assert detail['sourceId'] == pipeline_source['id']
    assert detail['candidateId'] == payload['candidateId']
    assert [event['action'] for event in detail['events']] == ['created']


def test_foreign_workspace_incident_id_collision_is_not_found(client, pipeline_source, service_headers):
    from datetime import UTC, datetime
    from app.db import SessionLocal
    from app.models import IncidentModel, OrganizationModel
    payload = _incident_payload(pipeline_source['id'], id='inc-foreign-collision')
    assert client.post('/v1/incidents', headers=service_headers, json=payload).status_code == 201
    with SessionLocal() as session:
        session.add(OrganizationModel(id='org-collision', name='Other', slug='collision',
                                      settings={}, created_at=datetime.now(UTC)))
        session.get(IncidentModel, payload['id']).org_id = 'org-collision'
        session.commit()
    try:
        response = client.post('/v1/incidents', headers=service_headers,
                               json={**payload, 'shortSummary': 'must not overwrite'})
        assert response.status_code == 404
        with SessionLocal() as session:
            assert session.get(IncidentModel, payload['id']).short_summary == payload['shortSummary']
    finally:
        with SessionLocal() as session:
            session.get(IncidentModel, payload['id']).org_id = 'org-demo'
            session.commit()
            session.delete(session.get(OrganizationModel, 'org-collision'))
            session.commit()


def test_insert_race_returns_retryable_conflict_without_duplicate_audit(
    client, pipeline_source, service_headers, monkeypatch,
):
    from sqlalchemy.orm import Session
    from app.models import IncidentModel
    payload = _incident_payload(pipeline_source['id'], id='inc-insert-race')
    assert client.post('/v1/incidents', headers=service_headers, json=payload).status_code == 201
    original_get = Session.get
    def missed_lookup(session, entity, ident, *args, **kwargs):
        # Reproduce the insert-race boundary: preflight sees no row, but the
        # unique key is present when the transaction commits.
        if entity is IncidentModel and ident == payload['id']:
            return None
        return original_get(session, entity, ident, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Session, 'get', missed_lookup)
        response = client.post('/v1/incidents', headers=service_headers, json=payload)
    assert response.status_code == 409
    assert response.headers['retry-after'] == '1'
    detail = client.get('/v1/incidents/' + payload['id'], headers=service_headers).json()
    assert [event['action'] for event in detail['events']] == ['created']
    assert client.post('/v1/incidents', headers=service_headers, json=payload).status_code == 201


def test_incident_filtering(client, pipeline_source, service_headers, viewer_headers):
    client.post(
        "/v1/incidents",
        headers=service_headers,
        json=_incident_payload(
            pipeline_source["id"],
            id="inc-filter-hk",
            category="Housekeeping",
            subcategory="bin_overflow",
            type="bin_overflow",
            severity="medium",
            candidateId="cand-filter",
        ),
    )
    by_category = client.get(
        "/v1/incidents", headers=viewer_headers, params={"category": "Housekeeping"}
    ).json()
    assert all(item["category"] == "Housekeeping" for item in by_category)
    assert any(item["id"] == "inc-filter-hk" for item in by_category)

    by_severity = client.get(
        "/v1/incidents",
        headers=viewer_headers,
        params={"severity": "critical", "sourceId": pipeline_source["id"]},
    ).json()
    assert all(item["severity"] == "critical" for item in by_severity)


def test_invalid_status_rejected(client, pipeline_source, service_headers, operator_headers):
    created = client.post(
        "/v1/incidents",
        headers=service_headers,
        json=_incident_payload(pipeline_source["id"], id="inc-badstatus"),
    )
    assert created.status_code == 201
    response = client.patch(
        "/v1/incidents/inc-badstatus/status",
        headers=operator_headers,
        json={"status": "made_up_status"},
    )
    assert response.status_code == 422


def test_comments_push_a_live_update_to_other_browsers(client, pipeline_source, service_headers,
                                                       operator_headers, monkeypatch):
    from app.routers import incidents as router
    created = client.post('/v1/incidents', headers=service_headers,
                          json=_incident_payload(pipeline_source['id'], id='inc-comment-live',
                                                 candidateId='cand-comment-live')).json()
    published = []
    monkeypatch.setattr(router, 'publish_event', lambda kind, data: published.append((kind, data)))
    response = client.post('/v1/incidents/inc-comment-live/comments', headers=operator_headers,
                           json={'body': 'Checked on camera'})
    assert response.status_code == 201
    assert [kind for kind, _ in published] == ['incident']
    assert published[0][1]['id'] == 'inc-comment-live'
    assert published[0][1]['updatedAt'] > created['updatedAt']


def test_timeline_says_what_a_pipeline_update_changed(client, pipeline_source, service_headers, operator_headers):
    payload = _incident_payload(pipeline_source['id'], id='inc-timeline-words', candidateId='cand-timeline-words',
                                reviewNotes=['AI review queued; measured rule incident remains active.'])
    client.post('/v1/incidents', headers=service_headers, json=payload)
    client.post('/v1/incidents', headers=service_headers, json={**payload, 'reviewNotes': [
        'AI review by qwen2.5vl:3b (2.1 s): image looks consistent with the measured event. Rule decision unchanged.']})
    client.post('/v1/incidents', headers=service_headers, json={**payload, 'reviewNotes': [
        'AI review unavailable: model did not answer in time.']})
    detail = client.get('/v1/incidents/inc-timeline-words', headers=operator_headers).json()
    notes = [event.get('note') for event in detail['events'] if event['action'] == 'pipeline_update']
    assert notes == ['AI review by qwen2.5vl:3b (2.1 s)', 'AI review unavailable: model did not answer in time']
