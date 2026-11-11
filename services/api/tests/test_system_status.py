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


def _exposition(observe_detector, observe_ai):
    from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

    det, ai = CollectorRegistry(), CollectorRegistry()
    req = Counter("smartops_detector_requests_total", "x", ["outcome"], registry=det)
    inf = Histogram("smartops_detector_inference_seconds", "x", buckets=(0.05, 0.1, 0.2, 0.5, 1), registry=det)
    rev = Counter("smartops_ai_reviews_total", "x", ["outcome", "reason"], registry=ai)
    sec = Histogram("smartops_ai_review_seconds", "x", buckets=(5, 10, 20, 30, 60), registry=ai)
    observe_detector(req, inf)
    observe_ai(rev, sec)
    return generate_latest(det).decode(), generate_latest(ai).decode()


def _serve_text(monkeypatch, detector_text, ai_text):
    from app.routers import system

    def get(url, timeout=None):
        if isinstance(detector_text, Exception) and "detector" in url:
            raise detector_text
        body = detector_text if "detector" in url else ai_text
        return httpx.Response(200, text=body, request=httpx.Request("GET", url))
    monkeypatch.setattr(system.httpx, "get", get)


def test_metrics_report_percentiles_and_shares_without_counts(client, viewer_headers, monkeypatch):
    def detector(req, inf):
        for value in [0.04] * 10 + [0.15] * 9 + [0.8]:
            inf.observe(value)
            req.labels("ok").inc()
        req.labels("error").inc(5)

    def ai(rev, sec):
        for value in [8] * 18 + [25, 50]:
            sec.observe(value)
        rev.labels("validated", "").inc(19)
        rev.labels("failed", "timeout").inc(1)

    _serve_text(monkeypatch, *_exposition(detector, ai))
    body = client.get("/v1/system/metrics", headers=viewer_headers).json()
    assert body["detector"]["p50Seconds"] == 0.05 and body["detector"]["p95Seconds"] == 0.2
    assert body["detector"]["outcomes"] == {"error": 20.0, "ok": 80.0}
    assert body["ai"]["p50Seconds"] == 10 and body["ai"]["p95Seconds"] == 30
    assert body["ai"]["outcomes"] == {"failed": 5.0, "validated": 95.0}
    assert "19" not in str(body["ai"]) and "25" not in str(body["detector"])


def test_metrics_need_minimum_samples_and_name_a_down_service(client, viewer_headers, monkeypatch):
    def few(rev, sec):
        sec.observe(9)
        rev.labels("validated", "").inc()

    _, ai_text = _exposition(lambda req, inf: None, few)
    _serve_text(monkeypatch, httpx.ConnectError("down"), ai_text)
    body = client.get("/v1/system/metrics", headers=viewer_headers).json()
    assert body["detector"] == {"error": "metrics unavailable (ConnectError)"}
    assert body["ai"] == {"p50Seconds": None, "p95Seconds": None, "outcomes": None}


def test_metrics_require_sign_in(client):
    assert client.get("/v1/system/metrics").status_code == 401
