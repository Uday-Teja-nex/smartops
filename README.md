# SmartOps

SmartOps turns camera streams into incidents that facility, security and
operations staff can act on. It's built for office towers, shopping malls and
campuses. It runs entirely on one laptop, and the same compose files move to a
Linux GPU server behind HTTPS (see [Deployment](docs/DEPLOYMENT_READINESS.md)).

How it decides, in order:

1. **Measure.** YOLO person/object detection, multi-object tracking
   (ByteTrack) and polygon zones drawn on each camera produce deterministic
   rule incidents: crowding, queue build-up, restricted or after-hours entry,
   loitering, unattended bags, blocked exits and camera health. An incident is
   saved within a second of the rule firing, with a snapshot and a pre/post
   clip.
2. **Review.** A vision-language model looks at the clean frame and adds a
   one-line scene, a consistent/doubtful/unclear verdict and suggested checks,
   labelled with the model name. It never changes the rule's decision. If no
   model is available, the incident says why.
3. **Act.** Operators acknowledge, assign, comment, resolve or mark false
   positives. Every action is audited and pushed live to other browsers.
   Telegram and webhook channels notify per workspace rule.

There is no face recognition, identity tracking or demographic inference.
Track IDs are anonymous and last only while a person is in view.

## Quick start (Windows, PowerShell)

Needs Docker Desktop. Optional: native [Ollama](https://ollama.com) with
`qwen2.5vl:3b` for local AI review.

```powershell
.\demo.ps1 up
```

This checks the machine, starts native Ollama if it's the AI provider,
starts the stack, runs migrations, seeds three demo workspaces, waits for the
recorded streams and prints `READY -> http://localhost:3000`. A normal start
takes about 30 s.

Sign in with password `smartops-demo`:

| Workspace | Accounts |
|---|---|
| Harborline Mall (has recorded footage) | `operator@mall.demo`, `admin@mall.demo`, `viewer@mall.demo` |
| Northpoint Office Tower | `operator@smartops.local`, `admin@smartops.local`, `viewer@smartops.local` |
| Riverside Campus | `operator@campus.demo`, `admin@campus.demo`, `viewer@campus.demo` |

Each workspace also has `supervisor@`, `security@` and `ehs@` accounts.

Other commands:

```powershell
.\demo.ps1 preflight
```

```powershell
.\demo.ps1 reset
```

```powershell
.\demo.ps1 status
```

```powershell
.\demo.ps1 backup
```

```powershell
.\demo.ps1 restore
```

```powershell
.\demo.ps1 down
```

- `preflight` explains in plain English anything that would ruin a demo:
  Docker stopped or crash-looping, VM memory, disk, port collisions, missing
  models or API key, missing footage, streams not publishing.
- `reset` returns all three workspaces to the freshly seeded state in about
  6 s.
- `backup` and `restore` cover the database and the evidence bucket.
- If Docker Desktop crash-loops with "The file cannot be accessed by the
  system", run `.\demo.ps1 fix-docker`. Never choose "Reset to factory
  defaults": it deletes all volumes.

## Footage and cameras

`sample-data/streams.json` lists recorded clips that `stream-publisher` loops
into mediamtx as RTSP streams (`rtsp://mediamtx:8554/<path>`). Cameras whose
path has footage are enabled by the seed; the rest say what they're waiting
for. Real IP cameras and phones connect by RTSP/RTMP URL through the same
pipeline. Provenance of every clip is recorded in
[sample-data/README.md](sample-data/README.md); see
[docs/FOOTAGE_SHOT_LIST.md](docs/FOOTAGE_SHOT_LIST.md) for what to record.

## AI review providers

Set in `.env`; switching needs no code change.

| `SMARTOPS_MODEL_PROVIDER` | Use |
|---|---|
| `ollama` (default) | Native Windows Ollama at `http://host.docker.internal:11434`. `qwen2.5vl:3b` runs on CPU here (it doesn't fit 4 GB of VRAM): about 2 s per short answer and about 25 s per full review once loaded. |
| `openrouter` | Hosted, free-tier models (`docs/FREE_API_SETUP.md`). The free tier allows 50 requests a day. |
| `openai-compatible` | Any OpenAI-style server: vLLM, LM Studio, a cloud GPU. |

`SMARTOPS_MODEL_FALLBACK=ollama` makes a hosted provider fall back to native
Ollama on rate limits, outages and timeouts. The detector backend is
`SMARTOPS_DETECTOR_BACKEND`: `ultralytics-cpu` (default), `ultralytics-cuda`
or `remote`.

## Checks

```powershell
npm run lint
```

```powershell
npx tsc --noEmit
```

```powershell
npm test
```

Run each Python service's tests separately, because their `app` packages
collide:

```powershell
.\.venv\Scripts\python.exe -m pytest services/api/tests -q
```

```powershell
.\.venv\Scripts\python.exe -m pytest services/video-ingest/tests -q
```

```powershell
.\.venv\Scripts\python.exe -m pytest services/orchestrator/tests -q
```

```powershell
.\.venv\Scripts\python.exe -m pytest services/detector/tests -q
```

## Documents

- [docs/AGENT_HANDOFF.md](docs/AGENT_HANDOFF.md): what works, what was
  measured, known limits.
- [docs/presentation/PRESENTATION_SCRIPT.md](docs/presentation/PRESENTATION_SCRIPT.md):
  the 10-minute client demo and its recovery table.
- [docs/DEPLOYMENT_READINESS.md](docs/DEPLOYMENT_READINESS.md): production and
  the cloud GPU move.
- [docs/DECISIONS/](docs/DECISIONS/): architecture decision records.
