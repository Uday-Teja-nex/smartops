"""Workspace user management and self-service passwords."""
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import AuthSessionModel, UserModel


def login(client, email, password):
    response = client.post("/v1/auth/login", json={"email": email, "password": password})
    return response


def test_admin_invites_changes_role_and_deactivates(client, admin_headers):
    invited = client.post("/v1/users", headers=admin_headers,
                          json={"email": "New.Guard@SmartOps.local", "name": "New Guard", "role": "operator"})
    assert invited.status_code == 201, invited.text
    body = invited.json()
    user_id, temp = body["user"]["id"], body["temporaryPassword"]
    assert body["user"]["email"] == "new.guard@smartops.local" and len(temp) >= 12
    assert client.post("/v1/users", headers=admin_headers,
                       json={"email": "new.guard@smartops.local", "name": "x", "role": "viewer"}).status_code == 409
    signed_in = login(client, "new.guard@smartops.local", temp)
    assert signed_in.status_code == 200
    guard = {"Authorization": "Bearer " + signed_in.json()["token"]}
    assert client.patch(f"/v1/users/{user_id}", headers=admin_headers, json={"role": "viewer"}).json()["role"] == "viewer"
    assert client.patch(f"/v1/users/{user_id}", headers=admin_headers, json={"active": False}).json()["active"] is False
    assert client.get("/v1/auth/me", headers=guard).status_code == 401          # sessions ended
    assert login(client, "new.guard@smartops.local", temp).status_code == 401


def test_admin_cannot_lock_themselves_out_and_others_cannot_manage(client, admin_headers, operator_headers):
    me = client.get("/v1/auth/me", headers=admin_headers).json()
    assert client.patch(f"/v1/users/{me['id']}", headers=admin_headers, json={"active": False}).status_code == 409
    assert client.patch(f"/v1/users/{me['id']}", headers=admin_headers, json={"role": "viewer"}).status_code == 409
    assert client.post("/v1/users", headers=operator_headers,
                       json={"email": "x@y.zz", "name": "x", "role": "admin"}).status_code == 403


def test_users_of_other_workspaces_are_not_found(client, admin_headers):
    with Session(engine) as session:
        mall_operator = session.scalars(select(UserModel).where(UserModel.email == "operator@mall.demo")).one()
    assert client.patch(f"/v1/users/{mall_operator.id}", headers=admin_headers, json={"active": False}).status_code == 404
    assert client.post(f"/v1/users/{mall_operator.id}/reset-password", headers=admin_headers).status_code == 404


def test_password_reset_and_self_change(client, admin_headers):
    from app.main import app
    invited = client.post("/v1/users", headers=admin_headers,
                          json={"email": "pw.user@smartops.local", "name": "Pw User", "role": "operator"}).json()
    reset = client.post(f"/v1/users/{invited['user']['id']}/reset-password", headers=admin_headers).json()
    assert login(client, "pw.user@smartops.local", invited["temporaryPassword"]).status_code == 401
    with TestClient(app) as browser_a, TestClient(app) as browser_b:
        a = {"Authorization": "Bearer " + login(browser_a, "pw.user@smartops.local", reset["temporaryPassword"]).json()["token"]}
        b = {"Authorization": "Bearer " + login(browser_b, "pw.user@smartops.local", reset["temporaryPassword"]).json()["token"]}
        assert browser_a.post("/v1/auth/password", headers=a, json={
            "currentPassword": "wrong", "newPassword": "a-new-strong-pass"}).status_code == 400
        assert browser_a.post("/v1/auth/password", headers=a, json={
            "currentPassword": reset["temporaryPassword"], "newPassword": "short"}).status_code == 422
        changed = browser_a.post("/v1/auth/password", headers=a, json={
            "currentPassword": reset["temporaryPassword"], "newPassword": "a-new-strong-pass"})
        assert changed.status_code == 204
        assert browser_a.get("/v1/auth/me", headers=a).status_code == 200     # this browser stays signed in
        assert browser_b.get("/v1/auth/me", headers=b).status_code == 401     # the other one is signed out
    assert login(client, "pw.user@smartops.local", "a-new-strong-pass").status_code == 200


def test_old_ended_sessions_are_pruned_at_sign_in(client):
    with Session(engine) as session:
        viewer = session.scalars(select(UserModel).where(UserModel.email == "viewer@smartops.local")).one()
        old = datetime.now(UTC) - timedelta(days=10)
        session.add(AuthSessionModel(id="ses-old-prune", org_id=viewer.org_id, user_id=viewer.id,
                                     refresh_hash="old-prune-hash", created_at=old, last_used_at=old,
                                     expires_at=old, revoked_at=old, revoked_reason="logout"))
        session.commit()
    assert login(client, "viewer@smartops.local", "smartops-demo").status_code == 200
    with Session(engine) as session:
        assert session.scalar(select(func.count()).where(AuthSessionModel.id == "ses-old-prune")) == 0
