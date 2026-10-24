"""Measure native Ollama on one real video frame; preserve raw measured results."""
import base64
import json
import time
from pathlib import Path

import cv2
import httpx

root = Path(__file__).resolve().parents[1]
capture = cv2.VideoCapture(str(root / "sample-data/input/first test video.mp4"))
ok, frame = capture.read()
capture.release()
if not ok:
    raise RuntimeError("Could not decode the supplied audit footage")
height, width = frame.shape[:2]
frame = cv2.resize(frame, (640, round(height * 640 / width)))
ok, encoded = cv2.imencode(".jpg", frame)
if not ok:
    raise RuntimeError("Could not encode audit frame")
schema = {
    "type": "object",
    "properties": {"description": {"type": "string"}},
    "required": ["description"],
    "additionalProperties": False,
}
results = []
with httpx.Client(base_url="http://127.0.0.1:11434", timeout=180) as client:
    for run in range(2):
        started = time.perf_counter()
        response = client.post("/api/chat", json={
            "model": "qwen2.5vl:3b", "stream": False, "format": schema,
            "keep_alive": "5m", "options": {"temperature": 0, "num_predict": 100, "num_ctx": 2048},
            "messages": [{"role": "user", "content": "Describe only the visible scene in one short sentence. Do not identify people. Return JSON.",
                          "images": [base64.b64encode(encoded).decode()]}],
        })
        elapsed = time.perf_counter() - started
        if response.is_error:
            failure = {"elapsedSeconds": elapsed, "status": response.status_code, "error": response.text}
            (root / "docs/verification/phase0-native-vlm-failure.json").write_text(json.dumps(failure, indent=2), encoding="utf-8")
            response.raise_for_status()
        body = response.json()
        content = json.loads(body["message"]["content"])
        assert isinstance(content.get("description"), str) and content["description"]
        results.append({"run": run, "elapsedSeconds": elapsed, "result": content,
                        "timings": {key: body.get(key) for key in ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration")}})
    report = {"model": "qwen2.5vl:3b", "frameWidth": 640, "runs": results, "loadedModels": client.get("/api/ps").json()}
output = root / "docs/verification/phase0-native-vlm.json"
output.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
