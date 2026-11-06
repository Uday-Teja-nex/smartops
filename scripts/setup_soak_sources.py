"""Register three soak cameras (soak-1..3) and pause the mall camera.

Usage: python scripts/setup_soak_sources.py [--teardown]
Run the publisher with docker-compose.soak.yml so soak-1..3 are published.
The soak cameras copy the mall store camera's zones, so the soak carries the
real rule/evidence load. Writes docs/verification/soak-sources.json.
--teardown disables the soak cameras and resumes the mall camera.
"""
import json
import sys
from pathlib import Path

import httpx

API = "http://localhost:8000"
TOKEN = {"X-Internal-Token": "smartops-internal-dev-token"}
STATE = Path("docs/verification/soak-sources.json")

with httpx.Client(base_url=API, timeout=10, headers=TOKEN) as client:
    sources = client.get("/v1/sources").json()
    store = next(s for s in sources if s["id"] == "src-mall-store")
    if "--teardown" in sys.argv:
        for source in sources:
            if "soak" in source.get("tags", []):
                client.post(f"/v1/sources/{source['id']}/disable").raise_for_status()
        client.post("/v1/sources/src-mall-store/resume").raise_for_status()
        print("soak cameras disabled; mall camera resumed")
        sys.exit(0)
    client.post("/v1/sources/src-mall-store/pause").raise_for_status()
    ids = []
    for index in (1, 2, 3):
        created = client.post("/v1/sources", json={
            "name": f"Soak stream {index}", "buildingId": "bldg-north-01", "floor": "L1", "zone": "Lobby Atrium",
            "sourceType": "rtsp", "sourceUri": f"rtsp://mediamtx:8554/soak-{index}", "enabled": True,
            "tags": ["soak", "engineering-verification"],
            "positionNotes": "Capacity soak: the supplied clip on an independent RTSP path.",
            "detectionConfig": store["detectionConfig"],
        })
        created.raise_for_status()
        ids.append(created.json()["id"])
    STATE.write_text(json.dumps({"sourceIds": ids}, indent=2))
    print(json.dumps({"sourceIds": ids}))
