from datetime import UTC, datetime


def test_live_observation_auth_validation_and_expiry(client, service_headers, viewer_headers, monkeypatch):
    from app.routers import live
    cache = {}
    class Cache:
        def set(self, key, value, ex):
            assert ex == 10
            cache[key] = value
        def get(self, key):
            return cache.get(key)
    monkeypatch.setattr(live, 'cache', Cache())
    monkeypatch.setattr(live, 'publish_event', lambda *args: None)
    sources = client.get('/v1/sources', headers=service_headers).json()
    path = f"/v1/sources/{sources[0]['id']}/observations"
    payload = {'sequence': 1, 'capturedAt': datetime.now(UTC).isoformat(),
               'width': 640, 'height': 360, 'detections': [], 'tracks': [], 'previewJpeg': None}
    assert client.post(path, headers=viewer_headers, json=payload).status_code == 403
    assert client.post(path, headers=service_headers, json=payload).status_code == 200
    assert client.get(path, headers=viewer_headers).json()['sequence'] == 1
    assert client.post(path, headers=service_headers, json={**payload, 'width': -1}).status_code == 422
    cache.clear()
    assert client.get(path, headers=viewer_headers).status_code == 404
