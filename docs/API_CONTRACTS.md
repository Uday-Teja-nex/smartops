# SmartOps API Contracts

Base URL (local): `http://localhost:8000`. All payloads are JSON with
camelCase fields. Interactive OpenAPI docs: `http://localhost:8000/docs`.

## Conventions

- **Auth**: `Authorization: Bearer <jwt>` for users; `X-Internal-Token:
  <token>` for pipeline services; `?token=<jwt>` accepted everywhere (used by
  SSE and `<video>` clients that cannot set headers).
- **Errors**: FastAPI shape `{"detail": "message"}` with proper status codes
  (401 unauthenticated, 403 role too low, 404 missing, 422 validation).
- **Versioning**: all business endpoints live under `/v1`. Breaking changes
  require `/v2` routes; additive fields are allowed within `/v1`.
- **Role requirements** below are minimums; `service` (internal token)
  counts as supervisor-level for pipeline writes but cannot use admin-only
  endpoints.

## Auth

| Endpoint | Method | Role | Notes |
|---|---|---|---|
| `/v1/auth/login` | POST | public | `{email, password}` → `{token, user}` |
| `/v1/auth/me` | GET | any | current principal |
| `/v1/users` | GET | admin | list users |

## Bootstrap & topology

| Endpoint | Method | Role |
|---|---|---|
| `/v1/bootstrap` | GET | viewer — `{buildings, sources, cameras (legacy), incidents, runtime}` |
| `/v1/buildings` | GET | viewer — buildings with nested floors/zones |
| `/v1/org` | GET | viewer — org profile + settings |
| `/v1/org/settings` | PUT | supervisor — merge `{settings: {...}}` |
| `/v1/config` | GET | viewer — runtime config (provider, orchestrator, evidence) |

## Sources

| Endpoint | Method | Role |
|---|---|---|
| `/v1/sources` | GET | viewer. Filters: `buildingId, status, sourceType, enabled, floor, zone` |
| `/v1/sources` | POST | supervisor |
| `/v1/sources/{id}` | GET / PATCH | viewer / supervisor |
| `/v1/sources/{id}` | DELETE | admin |
| `/v1/sources/{id}/pause` · `/resume` · `/disable` | POST | supervisor |
| `/v1/sources/{id}/health` | POST | supervisor/service — adapter health report |
| `/v1/sources/{id}/clip` | GET | viewer — raw local MP4 (file sources, dev only) |

Legacy `/v1/cameras` endpoints have been removed; use `/v1/sources`.

Create request (all optional fields may be omitted):

```json
{
  "name": "Lobby Atrium North",
  "buildingId": "bldg-north-01",
  "floorId": "flr-n01-l1",        // or "floor": "L1"
  "zoneId": "zone-n01-atrium",    // or "zone": "Lobby Atrium"
  "sourceType": "file",            // file | rtsp | onvif | webrtc
  "sourceUri": "/app/sample-data/input/lobby.mp4",
  "inputFormat": "mp4",
  "credentialsRef": "secret://vault/cam-01",
  "enabled": true,
  "tags": ["lobby", "priority"],
  "positionNotes": "Above north entrance, facing escalators",
  "detectionConfig": {"windowSeconds": 30, "sampleFramesPerWindow": 3, "minConfidence": 0.35}
}
```

Health report (`POST /v1/sources/{id}/health`):

```json
{"status": "failing", "lastError": "file not found", "latencyMs": 12.5,
 "adapter": "mp4-file", "details": {"durationSeconds": 128.4}}
```

Side effect: a transition to `failing` opens one rule-based System Health
incident (`modelProvider: "rule-engine"`); duplicates are suppressed while
one is open.

## Incidents

| Endpoint | Method | Role |
|---|---|---|
| `/v1/incidents` | GET | viewer. Filters: `status, category, severity, buildingId, sourceId, floor, zone, limit` |
| `/v1/incidents/{id}` | GET | viewer — detail incl. `events`, `comments`, `evidenceItems`, `detections` |
| `/v1/incidents` | POST | supervisor/service — idempotent upsert by `id`; re-submission updates draft fields but never rolls back operator lifecycle state |
| `/v1/incidents/{id}/acknowledge` · `/resolve` · `/false-positive` | PATCH | operator |
| `/v1/incidents/{id}/assign` | PATCH | operator — `{assignee}` |
| `/v1/incidents/{id}/status` | PATCH | operator — `{status, note?}` any lifecycle status |
| `/v1/incidents/{id}/comments` | POST | operator — `{body}` |

Illustrative contract only, not generated demo evidence. Incident record (list shape; detail adds `events/comments/evidenceItems/detections`):

```json
{
  "id": "inc-src-demo-lobby-8db6697ecd9c9354",
  "category": "Safety", "subcategory": "fallen_object", "type": "fallen_object",
  "severity": "medium", "confidence": 0.85, "status": "active",
  "buildingId": "bldg-north-01", "floor": "L1", "zone": "Lobby Atrium",
  "sourceId": "src-demo-lobby",
  "candidateId": "src-demo-lobby-8db6697ecd9c9354",
  "startTime": "...", "endTime": null, "ackTime": null, "resolvedTime": null,
  "slaDueAt": "...", "escalatedAt": null,
  "shortSummary": "...", "detailedNarrative": ["..."], "recommendedActions": ["..."],
  "reviewNotes": [],
  "evidence": {"thumbnailUrl": "/v1/evidence/evd-…/url", "clipUrl": "/v1/evidence/evd-…/url", "restricted": true},
  "assignedTo": null,
  "modelProvider": "ollama", "modelVersion": "qwen2.5vl:3b/llama3.2:3b",
  "detectionSummary": {"labels": {"person": 22}, "maxPersonsInFrame": 8,
                        "totalDetections": 22, "detectorStatus": "ran", "modelName": "yolov8n.pt"}
}
```

## Detections

| Endpoint | Method | Role |
|---|---|---|
| `/v1/detections` | POST | supervisor/service — `{detections: [...]}` batch |
| `/v1/detections` | GET | viewer. Filters: `candidateId, sourceId, limit` |

Detection: `{sourceId, candidateId, label, confidence, bbox:{x,y,w,h∈[0,1]},
frameTs, frameIndex, modelName}`.

## Evidence

| Endpoint | Method | Role |
|---|---|---|
| `/v1/evidence` | POST | supervisor/service — register uploaded object |
| `/v1/evidence` | GET | viewer. Filters: `incidentId, candidateId, sourceId` |
| `/v1/evidence/{id}/url` | GET | viewer — `{id, url, expiresInSeconds}` short-lived presigned URL |

Evidence URLs must always be fetched through `/url`; raw object keys are
never exposed. Role-scoped evidence restrictions bolt onto this single
endpoint.

## Pipeline & realtime

| Endpoint | Method | Role |
|---|---|---|
| `/v1/pipeline/status` | GET | viewer — `{queue, queued, deadLetter, recentStatuses[]}` |
| `/v1/incidents/stream` | GET (SSE) | viewer (via `?token=`) |

SSE protocol:

```
event: snapshot         // once on connect
data: {"incidents": [...], "sources": [...]}

event: incident         // on every incident create/update
data: {…incident record…}

event: source           // on source health/lifecycle change
data: {…source record…}

: heartbeat             // comment every ~15s while idle
```

## Operational

| Endpoint | Notes |
|---|---|
| `/health` | public liveness: `{status, service, model_provider, orchestrator}` |
| `/metrics` | Prometheus exposition (requests, latency histograms) |

## Other services (internal)

- Detector `POST :8200/v1/detect` — `{frames:[{frameIndex, timestampSeconds,
  imageBase64}], minConfidence}` → `{modelName, backend, inferenceMs,
  detections:[…]}`.
- Orchestrator `POST :8100/v1/candidates/review` — candidate + frames +
  `detectionContext` → `{createIncident, routeTo, incident?, notes[]}`.
  `GET :8100/v1/graph` describes the compiled LangGraph.

Frontend/backend integration rules: the frontend only consumes `/v1` API
contracts above; it never calls detector/orchestrator/Ollama directly.
