"""End-to-end smoke test against a RUNNING docker compose stack.

Path exercised:
  login -> register file source -> ingest discovers it -> worker samples ->
  detector persists detections -> orchestrator reviews -> incident visible
  via REST -> SSE stream delivers events.

Usage:
    python scripts/smoke.py [--api http://localhost:8000] [--timeout 900]

Notes:
  - Requires footage at sample-data/input/ (any .mp4).
  - On low-memory machines the VLM may be OOM-killed; the pipeline then
    produces an honest `human_review` incident, which still PASSES this
    smoke test (the product guarantee is "no fabricated detections", not
    "the laptop can always run a 3B VLM").
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request

DEMO_EMAIL = "supervisor@smartops.local"
DEMO_PASSWORD = "smartops-demo"


def call(api: str, path: str, token: str | None = None, payload: dict | None = None):
    request = urllib.request.Request(
        f"{api}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    api = args.api.rstrip("/")

    print("1) health check")
    health = call(api, "/health")
    assert health["status"] == "ok", health

    print("2) login as supervisor")
    token = call(api, "/v1/auth/login", payload={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})[
        "token"
    ]

    print("3) sources registered & healthy?")
    deadline = time.time() + args.timeout
    file_source = None
    while time.time() < deadline:
        sources = call(api, "/v1/sources", token)
        file_sources = [s for s in sources if s["sourceType"] == "file" and s["enabled"]]
        online = [s for s in file_sources if s["status"] in ("online", "processing")]
        if online:
            file_source = online[0]
            break
        time.sleep(5)
    assert file_source, "no enabled file source came online — is footage in sample-data/input?"
    print(f"   source {file_source['id']} online via {file_source['health'].get('adapter')}")

    print("4) waiting for detections from the YOLO stage…")
    detections = []
    while time.time() < deadline:
        detections = call(api, f"/v1/detections?sourceId={file_source['id']}&limit=5", token)
        if detections:
            break
        time.sleep(10)
    assert detections, "no detections persisted within timeout"
    print(f"   {len(detections)}+ detections, e.g. {detections[0]['label']} "
          f"@{detections[0]['confidence']:.2f} bbox={detections[0]['bbox']}")

    print("5) waiting for an incident from the review pipeline…")
    incident = None
    while time.time() < deadline:
        incidents = call(api, f"/v1/incidents?sourceId={file_source['id']}", token)
        if incidents:
            incident = incidents[0]
            break
        time.sleep(10)
    assert incident, "no incident persisted within timeout"
    print(
        f"   incident {incident['id']} status={incident['status']} "
        f"type={incident['type']} provider={incident['modelProvider']}"
    )

    print("6) incident detail carries audit trail + detections")
    detail = call(api, f"/v1/incidents/{incident['id']}", token)
    assert detail["events"], "no audit events on incident"

    print("7) SSE stream reachable and sends snapshot")
    query = urllib.parse.urlencode({"token": token})
    stream_request = urllib.request.Request(f"{api}/v1/incidents/stream?{query}")
    with urllib.request.urlopen(stream_request, timeout=30) as stream:
        first_chunk = stream.read(2048).decode(errors="replace")
    assert "event: snapshot" in first_chunk, first_chunk[:200]

    print("\nSMOKE TEST PASSED — source → detection → review → incident → stream")
    return 0


if __name__ == "__main__":
    sys.exit(main())
