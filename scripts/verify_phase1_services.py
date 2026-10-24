"""Read-only checks against rebuilt local services; never save access tokens."""
import json
from pathlib import Path

import httpx

with httpx.Client(timeout=10) as client:
    login = client.post("http://localhost:8000/v1/auth/login", json={
        "email": "operator@smartops.local", "password": "smartops-demo",
    })
    login.raise_for_status()
    with client.stream("GET", "http://localhost:8000/v1/incidents/stream", headers={
        "Authorization": f"Bearer {login.json()['token']}",
    }) as response:
        response.raise_for_status()
        first_line = next(response.iter_lines())
        assert first_line == "event: snapshot", first_line
    review = client.post("http://localhost:8100/v1/candidates/review", json={
        "candidateId": "verification-no-frames", "sourceUri": "/missing.mp4",
        "sourceName": "Verification", "observedAt": "2026-10-24T10:00:00Z",
        "camera": {"id": "src-demo-lobby", "buildingId": "bldg-north-01", "floor": "L1", "zone": "Lobby"},
        "frames": [],
    })
    review.raise_for_status()
    result = review.json()
    assert result["createIncident"] is False and result["incident"] is None, result
    assert result["notes"], result
report = {"sseFirstLine": first_line, "review": result}
Path("docs/verification/phase1-services-runtime.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
