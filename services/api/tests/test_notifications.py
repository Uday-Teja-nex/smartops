"""Notification rules, outbox delivery, retries and workspace isolation."""

from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import NotificationChannelModel, NotificationDeliveryModel
from app.notifications import channel_matches, telegram_text, webhook_signature, within_hours
from app.notifier import process_due


@pytest.fixture(scope="module")
def notify_source(client, service_headers):
    response = client.post("/v1/sources", headers=service_headers, json={
        "name": "Notify Cam", "buildingId": "bldg-north-01", "floor": "L1", "zone": "Lobby Atrium",
        "sourceType": "file", "sourceUri": "/app/sample-data/input/notify.mp4",
    })
    assert response.status_code == 201, response.text
    return response.json()


def incident(source_id, candidate, **overrides):
    payload = {
        "category": "Security", "type": "restricted_zone_entry", "severity": "high", "confidence": 1.0,
        "buildingId": "bldg-north-01", "floor": "L1", "zone": "Server room", "sourceId": source_id,
        "candidateId": candidate, "startTime": "2026-11-06T10:00:00Z",
        "shortSummary": "Person entered Server room", "detailedNarrative": [], "recommendedActions": [],
        "evidence": {"thumbnailUrl": "", "clipUrl": "", "restricted": False}, "modelProvider": "rule-engine", "modelVersion": "rules/1",
        "detectionSummary": {},
    }
    return payload | overrides


@pytest.fixture
def cleanup():
    yield
    with Session(engine) as session:
        for model in (NotificationDeliveryModel, NotificationChannelModel):
            for row in session.scalars(select(model)).all():
                session.delete(row)
        session.commit()


def fake_channel(**overrides):
    values = dict(enabled=True, min_severity="high", categories=[], active_hours=None)
    return SimpleNamespace(**(values | overrides))


def test_rule_matching_by_severity_category_and_hours():
    at = datetime(2026, 11, 6, 20, 30, tzinfo=UTC)  # 02:00 next day in Kolkata
    critical = SimpleNamespace(severity="critical", category="Security")
    low = SimpleNamespace(severity="low", category="Security")
    assert channel_matches(fake_channel(), critical, at)
    assert not channel_matches(fake_channel(), low, at)
    assert not channel_matches(fake_channel(enabled=False), critical, at)
    assert not channel_matches(fake_channel(categories=["Queue & Crowd"]), critical, at)
    overnight = {"start": "22:00", "end": "06:00", "timezone": "Asia/Kolkata"}
    assert within_hours(overnight, at)
    assert not within_hours(overnight, datetime(2026, 11, 6, 6, 30, tzinfo=UTC))  # 12:00 local
    assert not within_hours({"start": "09:00", "end": "18:00", "timezone": "Asia/Kolkata"}, at)


def test_channel_admin_api_masks_secrets_and_enforces_roles(client, admin_headers, supervisor_headers,
                                                            operator_headers, cleanup):
    body = {"kind": "telegram", "name": "Night guard phone", "minSeverity": "high",
            "config": {"botToken": "123456:SECRET-TOKEN-VALUE", "chatId": "987654321"}}
    assert client.post("/v1/notifications/channels", headers=operator_headers, json=body).status_code == 403
    assert client.post("/v1/notifications/channels", headers=supervisor_headers, json=body).status_code == 403
    created = client.post("/v1/notifications/channels", headers=admin_headers, json=body)
    assert created.status_code == 201, created.text
    assert "SECRET" not in created.text and "987654321" not in created.text
    assert created.json()["destination"] == "Telegram chat …4321"
    assert created.json()["configured"] == ["botToken", "chatId"]
    listed = client.get("/v1/notifications/channels", headers=supervisor_headers)
    assert listed.status_code == 200 and "SECRET" not in listed.text
    assert client.get("/v1/notifications/channels", headers=operator_headers).status_code == 403

    bad = client.post("/v1/notifications/channels", headers=admin_headers,
                      json={"kind": "telegram", "name": "x", "config": {"chatId": "1"}})
    assert bad.status_code == 422
    hours = client.post("/v1/notifications/channels", headers=admin_headers,
                        json={**body, "activeHours": {"start": "25:00", "end": "06:00"}})
    assert hours.status_code == 422
    channel_id = created.json()["id"]
    patched = client.patch(f"/v1/notifications/channels/{channel_id}", headers=admin_headers,
                           json={"enabled": False, "config": {"chatId": "111122223333"}})
    assert patched.json()["enabled"] is False and patched.json()["destination"].endswith("3333")
    with Session(engine) as session:
        stored = session.get(NotificationChannelModel, channel_id).config
    # Encrypted at rest: nothing readable in the database row, still usable by the notifier.
    from app.secret_box import open_
    assert list(stored) == ["_enc"] and "SECRET" not in stored["_enc"] and "111122223333" not in stored["_enc"]
    assert open_(stored) == {"botToken": "123456:SECRET-TOKEN-VALUE", "chatId": "111122223333"}


def test_new_incidents_enqueue_matching_channels_once(client, admin_headers, service_headers,
                                                       notify_source, cleanup):
    high = client.post("/v1/notifications/channels", headers=admin_headers, json={
        "kind": "webhook", "name": "Ops webhook", "minSeverity": "high",
        "config": {"url": "https://hooks.example.test/smartops", "secret": "s3cret"}}).json()
    client.post("/v1/notifications/channels", headers=admin_headers, json={
        "kind": "webhook", "name": "Critical only", "minSeverity": "critical",
        "config": {"url": "https://hooks.example.test/critical"}})
    created = client.post("/v1/incidents", headers=service_headers,
                          json=incident(notify_source["id"], "cand-notify-1", id="inc-notify-1"))
    assert created.status_code == 201, created.text
    # Re-submission (e.g. AI enrichment) must not notify again.
    again = client.post("/v1/incidents", headers=service_headers,
                        json=incident(notify_source["id"], "cand-notify-1", id="inc-notify-1",
                                      shortSummary="Enriched"))
    assert again.status_code == 201
    client.post("/v1/incidents", headers=service_headers,
                json=incident(notify_source["id"], "cand-notify-2", severity="medium"))
    with Session(engine) as session:
        rows = session.scalars(select(NotificationDeliveryModel)).all()
    assert [(row.incident_id, row.channel_id, row.status) for row in rows] == [("inc-notify-1", high["id"], "pending")]


def test_notifier_sends_retries_and_dead_letters(client, admin_headers, service_headers, notify_source, cleanup):
    channel = client.post("/v1/notifications/channels", headers=admin_headers, json={
        "kind": "webhook", "name": "Flaky", "minSeverity": "low",
        "config": {"url": "https://hooks.example.test/in", "secret": "s3cret"}}).json()
    client.post("/v1/incidents", headers=service_headers,
                json=incident(notify_source["id"], "cand-notify-3", id="inc-notify-3"))
    responses = iter([503, 200])
    received = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(request)
        return httpx.Response(next(responses))

    with httpx.Client(transport=httpx.MockTransport(handler)) as fake, Session(engine) as session:
        assert process_due(session, fake) == 1
        row = session.scalars(select(NotificationDeliveryModel)).one()
        assert (row.status, row.attempts, row.last_error) == ("pending", 1, "Webhook returned HTTP 503")
        row.next_attempt_at = datetime.now(UTC)
        session.commit()
        assert process_due(session, fake) == 1
        session.refresh(row)
        assert (row.status, row.attempts, row.last_error) == ("sent", 2, None)
    body = received[-1].content
    assert received[-1].headers["X-SmartOps-Signature"] == webhook_signature("s3cret", body)
    assert b'"incident.created"' in body and b'inc-notify-3' in body

    client.post("/v1/incidents", headers=service_headers,
                json=incident(notify_source["id"], "cand-notify-4", id="inc-notify-4"))
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404))) as fake, \
            Session(engine) as session:
        process_due(session, fake)
        dead = session.scalars(select(NotificationDeliveryModel).where(
            NotificationDeliveryModel.incident_id == "inc-notify-4")).one()
        assert (dead.status, dead.attempts) == ("dead", 1)
    assert channel["id"]


def test_telegram_failure_never_leaks_token(client, admin_headers, service_headers, notify_source, cleanup):
    client.post("/v1/notifications/channels", headers=admin_headers, json={
        "kind": "telegram", "name": "Phone", "minSeverity": "low",
        "config": {"botToken": "999:TOKEN-THAT-MUST-NOT-LEAK", "chatId": "42"}})
    client.post("/v1/incidents", headers=service_headers,
                json=incident(notify_source["id"], "cand-notify-5", id="inc-notify-5"))

    def boom(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/bot999:TOKEN-THAT-MUST-NOT-LEAK/sendMessage"
        raise httpx.ConnectError(f"cannot reach {request.url}")

    with httpx.Client(transport=httpx.MockTransport(boom)) as fake, Session(engine) as session:
        process_due(session, fake)
        row = session.scalars(select(NotificationDeliveryModel)).one()
    assert row.status == "pending" and "TOKEN" not in row.last_error
    assert row.last_error == "Telegram unreachable (ConnectError)"


def test_telegram_text_is_human_readable():
    text = telegram_text({"severity": "high", "typeLabel": "Restricted zone entry", "summary": "Person entered",
                          "zone": "Server room", "floor": "L1", "detectedBy": "rule-engine",
                          "url": "http://localhost:3000/incidents/inc-1"})
    assert text.splitlines()[0] == "[HIGH] Restricted zone entry"
    assert "Where: Server room · L1" in text and "Detected by: rule-engine" in text


def test_channels_and_deliveries_are_workspace_scoped(client, admin_headers, cleanup):
    from app.auth import Principal, get_current_principal
    from app.main import app
    from app.models import OrganizationModel
    created = client.post("/v1/notifications/channels", headers=admin_headers, json={
        "kind": "webhook", "name": "Demo org hook", "config": {"url": "https://hooks.example.test/a"}}).json()
    with Session(engine) as session:
        session.add(OrganizationModel(id="org-notify-other", name="Other", slug="notify-other",
                                      settings={}, created_at=datetime.now(UTC)))
        session.commit()
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        "other-admin", "Other", "o@example.test", "admin", "org-notify-other", "user")
    try:
        assert client.get("/v1/notifications/channels").json() == []
        assert client.get("/v1/notifications/deliveries").json() == []
        assert client.patch(f"/v1/notifications/channels/{created['id']}", json={"enabled": False}).status_code == 404
        assert client.delete(f"/v1/notifications/channels/{created['id']}").status_code == 404
        assert client.post(f"/v1/notifications/channels/{created['id']}/test").status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_principal, None)
        with Session(engine) as session:
            session.delete(session.get(OrganizationModel, "org-notify-other"))
            session.commit()
