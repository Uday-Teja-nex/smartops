"""System status names each failed component and what it means for operators."""
from unittest.mock import Mock

import httpx


def fake_get(responses):
    def get(url, timeout=None):
        for suffix, outcome in responses.items():
            if url.endswith(suffix):
                if isinstance(outcome, Exception):
                    raise outcome
                request = httpx.Request("GET", url)
                return httpx.Response(200, json=outcome, request=request)
        raise AssertionError(url)
    return get


def by_id(body):
    return {item["id"]: item for item in body["components"]}


def test_status_reports_healthy_components(client, viewer_headers, monkeypatch):
    import time
    import redis
    from app.routers import system
    monkeypatch.setattr(redis.Redis, "from_url", Mock(return_value=Mock(ping=Mock(), get=Mock(return_value=str(time.time())))))
    monkeypatch.setattr(system.httpx, "get", fake_get({
        "/health": {"backend": "ultralytics-cpu", "model": "yolov8n.pt"},
        "/v1/status": {"ok": True, "provider": "ollama", "model": "qwen2.5vl:3b", "detail": "loaded and warm",
                       "lastReview": {"ok": True, "secondsAgo": 12}},
        "/v3/paths/list": {"items": []},
    }))
    response = client.get("/v1/system/status", headers=viewer_headers)
    assert response.status_code == 200
    components = by_id(response.json())
    assert components["detector"]["detail"] == "ultralytics-cpu · yolov8n.pt"
    assert "last review OK 12 s ago" in components["ai"]["detail"]
    assert components["notifier"]["ok"] and components["database"]["ok"]


def test_status_names_what_is_down_and_the_operator_impact(client, viewer_headers, monkeypatch):
    import redis
    from app.routers import system
    monkeypatch.setattr(redis.Redis, "from_url", Mock(return_value=Mock(ping=Mock(), get=Mock(return_value=None))))
    monkeypatch.setattr(system.httpx, "get", fake_get({
        "/health": httpx.ConnectError("refused"),
        "/v1/status": {"ok": False, "provider": "openrouter", "model": "m", "detail": "hosted",
                       "lastReview": {"ok": False, "secondsAgo": 30, "reason": "model provider daily request limit reached"}},
        "/v3/paths/list": {"items": []},
    }))
    body = client.get("/v1/system/status", headers=viewer_headers).json()
    components = by_id(body)
    assert body["ok"] is False
    assert components["detector"]["impact"] == "Live detection is paused: no new incidents until it returns."
    assert "daily request limit" in components["ai"]["detail"]
    assert components["ai"]["impact"].startswith("Incidents still fire")
    assert components["notifier"]["detail"] == "no heartbeat in the last 15 s"


def test_status_requires_sign_in(client):
    assert client.get("/v1/system/status").status_code == 401
