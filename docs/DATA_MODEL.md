# SmartOps Data Model

Postgres is the source of truth. Schema is managed by Alembic
(`services/api/alembic/`); models live in `services/api/app/models/`.
IDs are prefixed strings (`org-`, `usr-`, `bldg-`, `flr-`, `zone-`, `src-`,
`det-`, `inc-`, `evt-`, `cmt-`, `evd-`).

## Entity relationship overview

```
organizations 1──* users
organizations 1──* buildings 1──* floors 1──* zones
organizations 1──* sources ──▶ buildings, floors?, zones?
organizations 1──* incidents ──▶ sources
organizations 1──* detections ──▶ sources        (linked to incidents via candidate_id)
organizations 1──* evidence_items ──▶ sources    (incident_id and/or candidate_id)
incidents 1──* incident_events   (audit trail)
incidents 1──* incident_comments
```

## Tables

### organizations
Tenant root. `settings` JSON holds org preferences
(`categoryThresholds`, `notificationPreferences`).

### users
`email` (unique), `password_hash` (PBKDF2-SHA256, self-describing format),
`role` ∈ `admin | supervisor | operator | viewer | security | ehs`, `active`.

### buildings / floors / zones
Physical topology. `zones.kind` ∈ `zone | room`. Sources and incidents also
carry denormalized `floor`/`zone` label strings so ingestion works before
structured topology is linked.

### sources
A registered video input.

| Column | Notes |
|---|---|
| `source_type` | `file` (working) · `rtsp` · `onvif` · `webrtc` (adapters pending) |
| `source_uri` | file path / stream URL |
| `input_format` | e.g. `mp4`, `h264` |
| `credentials_ref` | pointer to a secrets store — never raw credentials |
| `enabled` | operator intent |
| `status` | `online · offline · paused · failing · processing` |
| `health` | JSON: `lastSeen`, `lastError`, `latencyMs`, `adapter`, probe details |
| `tags` | JSON string array |
| `position_notes` | free text camera placement notes |
| `detection_config` | JSON: `windowSeconds`, `sampleFramesPerWindow`, `minConfidence`, `detectors` |

### detections
One row per YOLO detection. Normalized bbox (`bbox_x/y/w/h` ∈ [0,1]),
`frame_ts` (seconds into source), `frame_index`, `model_name`,
`candidate_id` (join key to the window and later the incident).

### incidents
Core product entity.

| Group | Columns |
|---|---|
| Classification | `category` (6-way), `subcategory`, `event_type`, `severity`, `confidence` |
| Lifecycle | `status` ∈ `active · acknowledged · assigned · in_progress · resolved · false_positive · escalated · human_review`, `start/end/ack/resolved` times, `sla_due_at`, `escalated_at`, `assigned_to` |
| Location | `building_id`, `floor`, `zone`, `source_id`, `candidate_id` |
| Content | `short_summary`, `detailed_narrative` (JSON list), `recommended_actions` (JSON list), `review_notes` (JSON list — why human review) |
| Model provenance | `model_provider` (`ollama` / `rule-engine`), `model_version`, `detection_summary` JSON |
| Evidence (legacy) | `evidence_thumbnail_url`, `evidence_clip_url`, `evidence_restricted` — API paths to presign endpoints; `evidence_items` is canonical |

### incident_events (audit)
`actor` (user "Name (email)" or `pipeline`), `action`
(`created`, `acknowledge`, `assign`, `status_change`, `comment`,
`false_positive`, `resolve`, `pipeline_update`), `from_status`, `to_status`,
`note`, `created_at`.

### incident_comments
`author`, `body`, `created_at`.

### evidence_items
Object-storage artifacts. `kind` ∈ `snapshot | thumbnail | clip | metadata`,
`object_key` (bucket path `{sourceId}/{candidateId}/…`), `content_type`,
dimensions/duration/size, `restricted`, `meta` JSON (e.g. clip
`windowStart`/`windowEnd`). Linked by `incident_id` and/or `candidate_id` —
the worker uploads before the incident row exists, so reads match on either.

## SLA defaults

Set at creation when the pipeline supplies none
(`services/api/app/routers/incidents.py`): critical 15m, high 60m,
medium 240m, low 1440m. The orchestrator supplies per-event-type SLAs from
its catalog (`services/orchestrator/app/catalog.py`).

## Migration policy

- Never edit migration `0001` retroactively; add new revisions.
- SQLite (`sqlite:///…`) skips Alembic and uses `create_all` — test-only mode.
- Migration `0001` drops the pre-Alembic demo tables (`incidents`, `cameras`,
  `buildings`) if present; production data never lived in them.
