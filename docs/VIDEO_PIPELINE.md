# SmartOps Video Pipeline

From registered source to persisted incident, and where each concern lives.

## Source lifecycle

```
registered (UI/API/autodiscovery)
   │  enabled?
   ▼
probe (adapter.probe, every SCAN_INTERVAL)
   ├─ ok        → status online, candidate windows enqueued
   ├─ failing   → status failing + rule-based System Health incident
   └─ pending   → status offline, health.lastError = "adapter not implemented"
paused / disabled → skipped by ingest, health preserved
```

Statuses: `online · processing · paused · failing · offline`. Operators
control `enabled`/`paused`; adapters control `online/failing/offline`.

## Source adapters (`services/video-ingest/app/adapters/`)

Contract (`base.py`):

```python
class SourceAdapter:
    def probe(self) -> HealthResult: ...
    def discover_candidates(self) -> list[CandidateWindow]: ...
```

| Adapter | Status | Notes |
|---|---|---|
| `mp4.py` | ✅ working | OpenCV probe (duration/fps/frames); splits footage into `windowSeconds` windows (default 30s, capped by `SMARTOPS_MAX_WINDOWS_PER_SOURCE`); window signature = file content key + window index → Redis dedupe. |
| `rtsp.py` | interface only | probe → explicit "RTSP adapter not implemented". Build: OPTIONS/DESCRIBE probe, rolling live windows from the stream buffer (FFmpeg/GStreamer). |
| `onvif.py` | interface only | Build: ONVIF discovery → media profile → delegate to RTSP adapter. |
| `webrtc.py` | interface only | Build: signaling probe + aiortc/gateway track buffer. |

Adding an adapter = one file + registry entry in `adapters/__init__.py`.
Nothing else changes: API, worker, orchestrator, and UI are already
multi-source.

MP4 autodiscovery (`SMARTOPS_AUTODISCOVER_MP4=true`): files in
`sample-data/input/*.mp4` that no source points at are registered via the
sources API, tagged `autodiscovered`.

## Candidate window job (Redis `smartops:candidate_jobs`)

```json
{
  "candidateId": "src-…-<sig>", "sourceUri": "…", "sourceName": "…",
  "windowIndex": 0, "windowStart": 0.0, "windowEnd": 30.0,
  "queuedAt": "…", "attempt": 0,
  "source": {"id", "buildingId", "floor", "zone", "detectionConfig"},
  "camera": {…legacy copy…}
}
```

Dedupe: `smartops:candidate_dedupe:{candidateId}` (24h TTL).
Status: `smartops:candidate_status:{candidateId}` — `queued → processing →
persisted | ignored | retrying | dead` (shown on the /monitoring page).

## Worker stages (`services/worker/app/main.py`)

1. **Sample** — OpenCV seeks evenly spaced frames within
   `[windowStart, windowEnd]`, resized to ≤640px, JPEG-encoded.
2. **Detect** — POST to detector; if `SMARTOPS_DETECTOR_BASE_URL` is empty
   the stage is `disabled`; on HTTP failure it is `unavailable`.
3. **Persist detections** — batch `POST /v1/detections`.
4. **Gate** (worker-side pre-gate; policy proper lives in the graph):
   - detector ran, zero detections → drop (`no_detections`)
   - only one person, no object hints → drop (`single_person_only`)
   - people ≥ `SMARTOPS_CROWD_PERSON_THRESHOLD` or object-hint labels
     (backpack/suitcase/chair/…) → forward
   - detector `disabled`/`unavailable` → forward (graph routes honestly)
5. **Review** — orchestrator call with frames + detection context.
6. **Evidence** — on incident creation: snapshot.jpg + thumbnail.jpg
   (320px) + clip.mp4 (ffmpeg trim of the window, ≤
   `SMARTOPS_EVIDENCE_CLIP_MAX_SECONDS`) uploaded to MinIO under
   `{sourceId}/{candidateId}/…`, registered via `POST /v1/evidence`;
   incident evidence URLs point at `/v1/evidence/{id}/url`.
7. **Persist incident** — `POST /v1/incidents` (idempotent by id).

Failure handling: any exception → retry with attempt counter; after
`SMARTOPS_JOB_MAX_ATTEMPTS` (3) → `smartops:candidate_jobs:dead`.
Evidence failures are non-fatal (incident keeps placeholder URLs).

## Frame budget & cost control

VLMs never see raw streams. Per window: `sampleFramesPerWindow` frames
(default 3) → YOLO (fast, CPU) → only gated windows reach the VLM. On a
laptop this reduces VLM calls by ~an order of magnitude.

## Configuration

Per-source `detectionConfig` overrides worker env defaults:
`windowSeconds`, `sampleFramesPerWindow`, `minConfidence`.
