"""Phone camera onboarding returns a publish URL and an enabled RTSP source."""


def test_supervisor_adds_a_phone_camera(client, supervisor_headers, monkeypatch):
    from app.routers import sources
    monkeypatch.setattr(sources.settings, "ingest_public_host", "192.168.1.50")
    response = client.post("/v1/sources/phone", headers=supervisor_headers, json={
        "name": "Uday's phone", "buildingId": "bldg-north-01", "floor": "L1", "zone": "Lobby Atrium"})
    assert response.status_code == 201, response.text
    body = response.json()
    path = body["publish"]["path"]
    assert path.startswith("phone-") and len(path) == len("phone-") + 6
    assert body["publish"]["rtmpUrl"] == f"rtmp://192.168.1.50:1935/{path}?user=phone&pass=smartops-phone"
    assert body["publish"]["lanHostConfigured"] is True
    source = body["source"]
    assert source["sourceType"] == "rtsp" and source["enabled"] is True
    assert source["sourceUri"] == f"rtsp://mediamtx:8554/{path}"
    second = client.post("/v1/sources/phone", headers=supervisor_headers, json={
        "name": "Second phone", "buildingId": "bldg-north-01", "floor": "L1", "zone": "Lobby Atrium"}).json()
    assert second["publish"]["path"] != path


def test_viewers_and_foreign_buildings_cannot_add_phones(client, viewer_headers, supervisor_headers):
    assert client.post("/v1/sources/phone", headers=viewer_headers, json={
        "name": "x", "buildingId": "bldg-north-01"}).status_code == 403
    assert client.post("/v1/sources/phone", headers=supervisor_headers, json={
        "name": "x", "buildingId": "bldg-mall-01"}).status_code in (404, 422)
