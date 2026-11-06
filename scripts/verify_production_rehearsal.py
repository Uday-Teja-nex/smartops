"""Verify the production overlay running locally behind Caddy (https://localhost).

Usage: python scripts/verify_production_rehearsal.py <admin-email> <minutes-to-wait-for-incident>
The admin password comes from SMARTOPS_ADMIN_PASSWORD. Uses the rehearsal's
internal CA, so TLS verification is disabled for this local check only.
Writes docs/verification/production-rehearsal.json.
"""
import json
import os
import socket
import sys
import time
from datetime import UTC, datetime

import httpx

BASE = "https://localhost"
email, wait_minutes = sys.argv[1], float(sys.argv[2])
checks: dict[str, object] = {"measuredAt": datetime.now(UTC).isoformat()}


def port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


with httpx.Client(base_url=BASE, verify=False, timeout=15) as client:
    plain = httpx.get("http://localhost/ready", follow_redirects=False, timeout=5)
    checks["httpRedirectsToHttps"] = plain.status_code in (301, 302, 308) and plain.headers.get("location", "").startswith("https://")
    console = client.get("/login")
    checks["consoleOverHttps"] = console.status_code
    checks["hsts"] = console.headers.get("strict-transport-security")
    checks["metricsBlocked"] = client.get("/metrics").status_code
    checks["ready"] = client.get("/ready").json()

    login = client.post("/v1/auth/login", json={"email": email, "password": os.environ["SMARTOPS_ADMIN_PASSWORD"]})
    cookie = login.headers.get("set-cookie", "")
    checks["login"] = login.status_code
    checks["refreshCookieSecureHttpOnlyStrict"] = all(flag in cookie.lower() for flag in ("secure", "httponly", "samesite=strict"))
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    checks["refreshOverHttps"] = client.post("/v1/auth/refresh").status_code

    # SSE through the proxy: the snapshot event must arrive unbuffered.
    ticket = client.post("/v1/auth/stream-ticket", headers=headers).json()["ticket"]
    started = time.monotonic()
    first_event = None
    with client.stream("GET", "/v1/incidents/stream", params={"ticket": ticket}, timeout=20) as stream:
        for line in stream.iter_lines():
            if line.startswith("event:"):
                first_event = line.split(":", 1)[1].strip()
                break
    checks["sseFirstEvent"] = {"event": first_event, "seconds": round(time.monotonic() - started, 2)}

    # A camera on the recorded stream, with the store's zones, must produce an
    # incident whose evidence is served through Caddy with a valid signature.
    # Production flow: the bootstrapped platform admin creates a client
    # workspace (with its building), whose own admin then adds a camera.
    created = client.post("/v1/workspaces", headers=headers, json={
        "name": "Rehearsal Mall", "accent": "#22c55e", "buildingName": "Rehearsal Mall",
        "floors": [{"level": "G", "name": "Ground", "zones": ["Store"]}],
        "password": os.environ["SMARTOPS_ADMIN_PASSWORD"]})
    checks["workspaceCreate"] = created.status_code
    admin = next(a["email"] for a in created.json()["accounts"] if a["role"] == "admin")
    login = client.post("/v1/auth/login", json={"email": admin, "password": os.environ["SMARTOPS_ADMIN_PASSWORD"]})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    building = client.get("/v1/buildings", headers=headers).json()
    checks["buildings"] = len(building)
    if building:
        zones = [{"id": "Checkout queue", "polygon": [[0.0, 0.3], [0.33, 0.3], [0.33, 1.0], [0.0, 1.0]],
                  "rules": [{"type": "queue_build_up", "threshold": 1, "durationSeconds": 8}]},
                 {"id": "Front aisle", "polygon": [[0.45, 0.45], [1.0, 0.45], [1.0, 1.0], [0.45, 1.0]],
                  "rules": [{"type": "crowding", "threshold": 2, "durationSeconds": 5}]}]
        floor = (building[0].get("floors") or [{}])[0]
        camera = client.post("/v1/sources", headers=headers, json={
            "name": "Rehearsal store camera", "buildingId": building[0]["id"],
            "floorId": floor.get("id"), "floor": floor.get("level") or "G", "zone": "Store",
            "sourceType": "rtsp", "sourceUri": "rtsp://mediamtx:8554/mall-store", "detectionConfig": {"zones": zones}})
        checks["cameraCreate"] = camera.status_code
        deadline = time.monotonic() + wait_minutes * 60
        evidence = []
        while time.monotonic() < deadline and not evidence:
            time.sleep(10)
            evidence = [item for item in client.get("/v1/evidence", headers=headers).json() if item["kind"] == "clip"]
        checks["incidents"] = len(client.get("/v1/incidents", headers=headers).json())
        if evidence:
            url = client.get(f"/v1/evidence/{evidence[0]['id']}/url", headers=headers).json()["url"]
            checks["evidenceUrlHost"] = httpx.URL(url).host + httpx.URL(url).path[:20]
            clip = httpx.get(url, verify=False, timeout=30)
            checks["evidenceDownloadThroughCaddy"] = {"status": clip.status_code, "bytes": len(clip.content)}

checks["directPortsClosed"] = {port: not port_open(port) for port in (3000, 8000, 8100, 8200, 9000, 9001, 9997)}
print(json.dumps(checks, indent=2))
with open("docs/verification/production-rehearsal.json", "w", encoding="utf-8") as handle:
    json.dump(checks, handle, indent=2)
