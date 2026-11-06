"""Platform admins create a client workspace in one request; nobody else can."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import OrganizationModel, SourceModel, UserModel

BODY = {
    "name": "Acme Mall", "accent": "#ff7a00", "buildingName": "Acme Mall East", "address": "1 Acme Road",
    "floors": [{"level": "G", "name": "Ground", "zones": ["Food court queue", "Main entrance"]},
               {"level": "L1", "name": "Retail", "zones": []}],
    "password": "prospect-demo-1",
}


def test_platform_admin_creates_a_ready_to_demo_workspace(client, admin_headers, service_headers):
    template = client.post("/v1/sources", headers=service_headers, json={
        "name": "Store template", "buildingId": "bldg-north-01", "floor": "L1", "zone": "Lobby Atrium",
        "sourceType": "rtsp", "sourceUri": "rtsp://mediamtx:8554/mall-store",
        "detectionConfig": {"zones": [{"id": "Checkout queue", "polygon": [[0, 0], [1, 0], [1, 1]],
                                        "rules": [{"type": "queue_build_up", "threshold": 1}]}]}}).json()
    caps = client.get("/v1/workspaces/capabilities", headers=admin_headers).json()
    assert caps["canCreateWorkspaces"] is True
    response = client.post("/v1/workspaces", headers=admin_headers,
                           json={**BODY, "copyCameraId": template["id"], "addPhoneCamera": True})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"] == "org-acme-mall"
    assert [a["email"] for a in body["accounts"]] == ["admin@acme-mall.demo", "operator@acme-mall.demo",
                                                    "viewer@acme-mall.demo"]
    assert body["cameras"] == ["Store template", "Phone camera"]
    login = client.post("/v1/auth/login", json={"email": "operator@acme-mall.demo", "password": "prospect-demo-1"})
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["token"]}
    org = client.get("/v1/org", headers=headers).json()
    assert org["name"] == "Acme Mall" and org["settings"]["accent"] == "#ff7a00"
    sources = client.get("/v1/sources", headers=headers).json()
    copied = next(s for s in sources if s["name"] == "Store template")
    assert copied["sourceUri"] == "rtsp://mediamtx:8554/mall-store"
    assert copied["detectionConfig"]["zones"][0]["id"] == "Checkout queue"
    assert template["id"] not in {s["id"] for s in sources}
    # A second workspace with the same name gets its own slug, not a collision.
    again = client.post("/v1/workspaces", headers=admin_headers, json=BODY)
    assert again.status_code == 201 and again.json()["id"] != "org-acme-mall"


def test_only_platform_admins_create_workspaces(client, supervisor_headers):
    from tests.conftest import login
    mall_admin = login(client, "admin@mall.demo")
    assert client.get("/v1/workspaces/capabilities", headers=mall_admin).json() == {
        "canCreateWorkspaces": False, "copyableCameras": []}
    assert client.post("/v1/workspaces", headers=mall_admin, json=BODY).status_code == 403
    assert client.post("/v1/workspaces", headers=supervisor_headers, json=BODY).status_code == 403


def test_workspace_input_is_validated(client, admin_headers):
    assert client.post("/v1/workspaces", headers=admin_headers, json={**BODY, "accent": "orange"}).status_code == 422
    assert client.post("/v1/workspaces", headers=admin_headers, json={**BODY, "password": "short"}).status_code == 422
    assert client.post("/v1/workspaces", headers=admin_headers, json={**BODY, "timezone": "Mars/Base"}).status_code == 422
    assert client.post("/v1/workspaces", headers=admin_headers, json={**BODY, "copyCameraId": "nope"}).status_code == 404
