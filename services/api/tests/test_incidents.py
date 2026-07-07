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
    assert incident["cameraId"] == incident["sourceId"]  # legacy alias

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
