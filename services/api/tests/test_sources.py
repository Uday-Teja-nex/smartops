def _source_payload(**overrides):
    payload = {
        "name": "Test Camera",
        "buildingId": "bldg-north-01",
        "floor": "L1",
        "zone": "Lobby Atrium",
        "sourceType": "file",
        "sourceUri": "/app/sample-data/input/test.mp4",
        "tags": ["test"],
        "detectionConfig": {"windowSeconds": 30},
    }
    payload.update(overrides)
    return payload


def test_viewer_cannot_create_source(client, viewer_headers):
    response = client.post("/v1/sources", headers=viewer_headers, json=_source_payload())
    assert response.status_code == 403


def test_source_crud_lifecycle(client, supervisor_headers, viewer_headers):
    created = client.post("/v1/sources", headers=supervisor_headers, json=_source_payload())
    assert created.status_code == 201, created.text
    source = created.json()
    assert source["status"] == "offline"
    assert source["floor"] == "L1"
    source_id = source["id"]

    listed = client.get("/v1/sources", headers=viewer_headers)
    assert any(item["id"] == source_id for item in listed.json())

    updated = client.patch(
        f"/v1/sources/{source_id}",
        headers=supervisor_headers,
        json={"name": "Renamed Camera", "tags": ["a", "b"]},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed Camera"
    assert updated.json()["tags"] == ["a", "b"]

    paused = client.post(f"/v1/sources/{source_id}/pause", headers=supervisor_headers)
    assert paused.json()["status"] == "paused"

    resumed = client.post(f"/v1/sources/{source_id}/resume", headers=supervisor_headers)
    assert resumed.json()["status"] == "offline"
    assert resumed.json()["enabled"] is True

    disabled = client.post(f"/v1/sources/{source_id}/disable", headers=supervisor_headers)
    assert disabled.json()["enabled"] is False


def test_source_topology_validation(client, supervisor_headers):
    response = client.post(
        "/v1/sources",
        headers=supervisor_headers,
        json=_source_payload(buildingId="bldg-does-not-exist"),
    )
    assert response.status_code == 404

    response = client.post(
        "/v1/sources",
        headers=supervisor_headers,
        json=_source_payload(floorId="flr-s02-l5", buildingId="bldg-north-01"),
    )
    assert response.status_code == 400  # floor belongs to the other building

    response = client.post(
        "/v1/sources",
        headers=supervisor_headers,
        json=_source_payload(floor=None, zone=None),
    )
    assert response.status_code == 422


def test_structured_topology_resolves_labels(client, supervisor_headers):
    response = client.post(
        "/v1/sources",
        headers=supervisor_headers,
        json=_source_payload(
            floor=None,
            zone=None,
            floorId="flr-n01-l1",
            zoneId="zone-n01-elev",
        ),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["floor"] == "L1"
    assert body["zone"] == "Elevator Bank"


def test_health_report_updates_status_and_creates_rule_incident(
    client, supervisor_headers, service_headers, viewer_headers
):
    created = client.post(
        "/v1/sources", headers=supervisor_headers, json=_source_payload(name="Failing Cam")
    )
    source_id = created.json()["id"]

    ok = client.post(
        f"/v1/sources/{source_id}/health",
        headers=service_headers,
        json={"status": "online", "adapter": "mp4-file", "latencyMs": 12.5},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "online"
    assert ok.json()["health"]["adapter"] == "mp4-file"

    failing = client.post(
        f"/v1/sources/{source_id}/health",
        headers=service_headers,
        json={"status": "failing", "lastError": "file not found", "adapter": "mp4-file"},
    )
    assert failing.json()["status"] == "failing"

    incidents = client.get(
        "/v1/incidents",
        headers=viewer_headers,
        params={"category": "System Health", "sourceId": source_id},
    ).json()
    assert len(incidents) == 1
    assert incidents[0]["modelProvider"] == "rule-engine"
    assert incidents[0]["type"] == "camera_offline"

    # A second failing report must not duplicate the open incident.
    client.post(
        f"/v1/sources/{source_id}/health",
        headers=service_headers,
        json={"status": "failing", "lastError": "still broken", "adapter": "mp4-file"},
    )
    incidents = client.get(
        "/v1/incidents",
        headers=viewer_headers,
        params={"category": "System Health", "sourceId": source_id},
    ).json()
    assert len(incidents) == 1


def test_paused_source_keeps_lifecycle_status_on_health_report(
    client, supervisor_headers, service_headers
):
    created = client.post(
        "/v1/sources", headers=supervisor_headers, json=_source_payload(name="Paused Cam")
    )
    source_id = created.json()["id"]
    client.post(f"/v1/sources/{source_id}/pause", headers=supervisor_headers)

    reported = client.post(
        f"/v1/sources/{source_id}/health",
        headers=service_headers,
        json={"status": "online", "adapter": "mp4-file"},
    )
    assert reported.json()["status"] == "paused"


def test_delete_source_requires_admin(client, supervisor_headers, admin_headers):
    created = client.post(
        "/v1/sources", headers=supervisor_headers, json=_source_payload(name="Doomed Cam")
    )
    source_id = created.json()["id"]
    assert (
        client.delete(f"/v1/sources/{source_id}", headers=supervisor_headers).status_code == 403
    )
    assert client.delete(f"/v1/sources/{source_id}", headers=admin_headers).status_code == 204


def test_legacy_camera_alias_removed(client, service_headers):
    assert client.get("/v1/cameras", headers=service_headers).status_code == 404
    bootstrap = client.get("/v1/bootstrap", headers=service_headers).json()
    assert "sources" in bootstrap
    assert "cameras" not in bootstrap


def test_delivery_health_is_persisted_for_monitoring(client, service_headers, viewer_headers):
    created = client.post('/v1/sources', headers=service_headers, json=_source_payload(name='Delivery telemetry'))
    source_id = created.json()['id']
    counts = {'pendingIncidents': 2, 'rejectedIncidentVersions': 3, 'pendingReviews': 4}
    reported = client.post(f'/v1/sources/{source_id}/health', headers=service_headers,
                           json={'status': 'processing', 'adapter': 'continuous-rtsp', 'details': counts})
    assert reported.status_code == 200
    saved = client.get(f'/v1/sources/{source_id}', headers=viewer_headers).json()
    assert {key: saved['health'][key] for key in counts} == counts

def test_offline_and_image_quality_incidents_are_broadcast_and_distinct(client, supervisor_headers, service_headers, viewer_headers, monkeypatch):
    from app.routers import sources
    broadcasts = []
    monkeypatch.setattr(sources, 'publish_event', lambda kind, payload: broadcasts.append((kind, payload)))
    created = client.post('/v1/sources', headers=supervisor_headers, json=_source_payload(name='Quality test'))
    source_id = created.json()['id']
    path = f'/v1/sources/{source_id}/health'
    response = client.post(path, headers=service_headers, json={'status': 'offline', 'adapter': 'continuous-rtsp', 'lastError': 'No fresh frames'})
    assert response.status_code == 200
    incidents = [payload for kind, payload in broadcasts if kind == 'incident']
    assert len(incidents) == 1
    assert incidents[0]['type'] == 'camera_offline'
    assert incidents[0]['evidence']['clipUrl'] == ''
    broadcasts.clear()
    response = client.post(path, headers=service_headers, json={'status': 'failing', 'adapter': 'continuous-rtsp', 'details': {'issues': ['camera_low_light', 'camera_obscured'], 'meanLuminance': 0}})
    assert response.status_code == 200
    incidents = [payload for kind, payload in broadcasts if kind == 'incident']
    assert {incident['type'] for incident in incidents} == {'camera_low_light', 'camera_obscured'}
    assert all(incident['detectionSummary']['meanLuminance'] == 0 for incident in incidents)
