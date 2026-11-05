"""Measure live AI enrichment on real pipeline incidents.

Usage: python scripts/measure_enrichment.py <email> <minutes> <output.json>
Polls the API every 2 s. For every incident created during the run it
records when the incident first appeared, when its AI review (or an
"AI review unavailable" note) first appeared, the reported model latency and
the outcome. Writes all raw rows plus a summary (validated share, p50/p95).
"""
import json
import statistics
import sys
import time
from datetime import datetime

import httpx

email, minutes, output = sys.argv[1], float(sys.argv[2]), sys.argv[3]
api = httpx.Client(base_url="http://localhost:8000", timeout=10)


def sign_in():
    response = api.post("/v1/auth/login", json={"email": email, "password": "smartops-demo"})
    response.raise_for_status()
    api.headers["Authorization"] = "Bearer " + response.json()["token"]


def review_state(incident):
    for note in incident.get("reviewNotes") or []:
        if note.startswith("AI review by "):
            return "validated", note
        if note.startswith("AI review unavailable"):
            return "unavailable", note
    return None, None


sign_in()
started = time.time()
known = {item["id"] for item in api.get("/v1/incidents").json()}
rows: dict[str, dict] = {}
deadline = started + minutes * 60
while time.time() < deadline or any(row["outcome"] is None for row in rows.values()):
    if time.time() > deadline + 120:
        break  # stop waiting for stragglers after two extra minutes
    response = api.get("/v1/incidents")
    if response.status_code == 401:
        sign_in()
        continue
    now = time.time()
    for incident in response.json():
        if incident["id"] in known:
            continue
        row = rows.setdefault(incident["id"], {
            "id": incident["id"], "type": incident["type"], "firstSeen": now,
            "createdAt": incident.get("createdAt"), "outcome": None})
        if row["outcome"] is None:
            outcome, note = review_state(incident)
            if outcome:
                review = (incident.get("detectionSummary") or {}).get("aiReview") or {}
                row.update(outcome=outcome, note=note, reviewSeen=now,
                           secondsFromIncident=round(now - row["firstSeen"], 1),
                           model=review.get("model"), modelLatencyMs=review.get("latencyMs"))
    time.sleep(2)

done = [row for row in rows.values() if row["outcome"]]
validated = [row for row in done if row["outcome"] == "validated"]
delays = sorted(row["secondsFromIncident"] for row in done)


def percentile(values, q):
    if not values:
        return None
    index = min(len(values) - 1, max(0, round(q * (len(values) - 1))))
    return values[index]


summary = {
    "measuredAt": datetime.now().isoformat(timespec="seconds"),
    "workspaceUser": email,
    "minutes": minutes,
    "incidents": len(rows),
    "reviewed": len(done),
    "validated": len(validated),
    "validatedShare": round(len(validated) / len(done), 3) if done else None,
    "neverReviewed": [row["id"] for row in rows.values() if not row["outcome"]],
    "secondsIncidentToReview": {"p50": percentile(delays, .5), "p95": percentile(delays, .95),
                                "max": delays[-1] if delays else None},
    "modelLatencyMs": {"median": statistics.median([r["modelLatencyMs"] for r in validated if r["modelLatencyMs"]])
                       if validated else None},
    "unavailableReasons": sorted({row["note"] for row in done if row["outcome"] == "unavailable"}),
}
with open(output, "w", encoding="utf-8") as handle:
    json.dump({"summary": summary, "rows": list(rows.values())}, handle, indent=2)
print(json.dumps(summary, indent=2))
