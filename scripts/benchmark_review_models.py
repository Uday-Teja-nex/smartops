"""Compare local vision models on the real incident-review contract.

Usage: python scripts/benchmark_review_models.py model [model ...]
For each model: warm-load with the orchestrator's runner options, then review
8 distinct 320 px frames from the supplied clip with the production prompt and
JSON schema. Records validated share, latency and the scene text, and writes
docs/verification/review-model-benchmark.json.
"""
import base64
import json
import statistics
import sys
import time
from pathlib import Path

import cv2
import httpx

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "services" / "orchestrator"))
from app.enrichment import ModelOutput, enrich, EnrichmentRequest  # noqa: E402
from app.providers.ollama import LOAD_OPTIONS, OllamaModelProvider  # noqa: E402

capture = cv2.VideoCapture(str(root / "sample-data/input/first test video.mp4"))
frames = []
for index in range(8):
    capture.set(cv2.CAP_PROP_POS_FRAMES, 60 + index * 170)
    ok, frame = capture.read()
    frame = cv2.resize(frame, (320, round(frame.shape[0] * 320 / frame.shape[1])), interpolation=cv2.INTER_AREA)
    frames.append(base64.b64encode(cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])[1]).decode())

report = {"frames": len(frames), "options": LOAD_OPTIONS, "models": {}}
for model in sys.argv[1:]:
    started = time.perf_counter()
    httpx.post("http://127.0.0.1:11434/api/generate", timeout=600,
               json={"model": model, "prompt": "", "keep_alive": "10m", "options": LOAD_OPTIONS})
    load_seconds = round(time.perf_counter() - started, 1)
    provider = OllamaModelProvider("http://127.0.0.1:11434", model, model, timeout_seconds=60)
    runs = []
    for index, image in enumerate(frames):
        t = time.perf_counter()
        try:
            result = enrich(provider, EnrichmentRequest(incidentId=f"bench-{index}", eventType="crowding",
                                                        measuredSummary="3 people in Front aisle for 5s",
                                                        imageBase64=image))
            runs.append({"ok": True, "seconds": round(time.perf_counter() - t, 1), "verdict": result.verdict,
                         "scene": result.scene})
        except Exception as exc:  # noqa: BLE001
            runs.append({"ok": False, "seconds": round(time.perf_counter() - t, 1), "error": f"{type(exc).__name__}: {str(exc)[:120]}"})
        print(model, json.dumps(runs[-1]), flush=True)
    ok = [r["seconds"] for r in runs if r["ok"]]
    report["models"][model] = {"loadSeconds": load_seconds, "validated": f"{len(ok)}/{len(runs)}",
                               "medianSeconds": statistics.median(ok) if ok else None,
                               "maxSeconds": max(ok) if ok else None, "runs": runs}
    httpx.post("http://127.0.0.1:11434/api/generate", json={"model": model, "keep_alive": 0}, timeout=60)

(root / "docs/verification/review-model-benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({m: {k: v for k, v in r.items() if k != "runs"} for m, r in report["models"].items()}, indent=2))
