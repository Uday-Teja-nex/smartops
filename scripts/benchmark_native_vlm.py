"""Benchmark native Ollama vision review on one real frame (GPU placement included).

Usage: python scripts/benchmark_native_vlm.py [model] [runs]
Writes docs/verification/native-ollama-gpu-<model>.json with every raw timing,
the validated/invalid outcome of each run and the VRAM residency from /api/ps.
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
model = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5vl:3b"
runs = int(sys.argv[2]) if len(sys.argv) > 2 else 5

capture = cv2.VideoCapture(str(root / "sample-data/input/first test video.mp4"))
capture.set(cv2.CAP_PROP_POS_FRAMES, 150)
ok, frame = capture.read()
capture.release()
if not ok:
    raise RuntimeError("Could not decode benchmark footage")
height, width = frame.shape[:2]
frame = cv2.resize(frame, (640, round(height * 640 / width)))
ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
image = base64.b64encode(encoded).decode()

schema = {
    "type": "object",
    "properties": {
        "scene": {"type": "string"},
        "verdict": {"type": "string", "enum": ["confirm", "doubt", "unclear"]},
        "people_visible": {"type": "integer"},
    },
    "required": ["scene", "verdict", "people_visible"],
    "additionalProperties": False,
}
prompt = ("You are reviewing a security camera frame. "
          "A rule engine flagged possible crowding. Return JSON: scene = one short factual sentence describing what you see (no identities), verdict = confirm, doubt or unclear for crowding, "
          "people_visible = integer count.")


def valid(content: dict) -> bool:
    return (isinstance(content.get("scene"), str) and 0 < len(content["scene"]) <= 300
            and content.get("verdict") in {"confirm", "doubt", "unclear"}
            and isinstance(content.get("people_visible"), int) and 0 <= content["people_visible"] < 500)


results = []
with httpx.Client(base_url="http://127.0.0.1:11434", timeout=120) as client:
    for run in range(runs):
        started = time.perf_counter()
        entry = {"run": run}
        try:
            response = client.post("/api/chat", json={
                "model": model, "stream": False, "format": schema, "keep_alive": "10m",
                "options": {"temperature": 0, "num_predict": 160, "num_ctx": 2048, "num_batch": 32},
                "messages": [{"role": "user", "content": prompt, "images": [image]}],
            })
            entry["status"] = response.status_code
            if response.is_error:
                entry["error"] = response.text[:500]
            else:
                body = response.json()
                try:
                    content = json.loads(body["message"]["content"])
                    entry["validated"] = valid(content)
                    entry["result"] = content
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    entry["validated"] = False
                    entry["error"] = f"unparseable: {exc}"
                entry["timings"] = {k: body.get(k) for k in (
                    "total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration",
                    "eval_count", "eval_duration")}
        except httpx.HTTPError as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
        entry["elapsedSeconds"] = round(time.perf_counter() - started, 3)
        results.append(entry)
        print(json.dumps(entry), flush=True)
    loaded = client.get("/api/ps").json()

warm = [r["elapsedSeconds"] for r in results[1:] if r.get("validated")]
report = {
    "model": model,
    "measuredAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "frameWidth": 640,
    "options": {"num_ctx": 2048, "num_batch": 32, "num_predict": 160},
    "runs": results,
    "validatedRuns": sum(1 for r in results if r.get("validated")),
    "coldSeconds": results[0]["elapsedSeconds"],
    "warmMedianSeconds": statistics.median(warm) if warm else None,
    "warmMaxSeconds": max(warm) if warm else None,
    "loadedModels": [{"name": m.get("name"), "size": m.get("size"), "size_vram": m.get("size_vram")}
                     for m in loaded.get("models", [])],
}
safe = model.replace(":", "-").replace("/", "-")
output = root / f"docs/verification/native-ollama-gpu-{safe}.json"
output.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in report.items() if k != "runs"}, indent=2))
