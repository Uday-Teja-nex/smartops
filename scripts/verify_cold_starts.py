"""Destructive local-demo check: reset this Compose project's volumes three times.

Back up any wanted database/evidence first. Never use against production.
The optional Docker Ollama profile is excluded; native Ollama is independent.
"""
import argparse
import json
import subprocess
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/verification"


def compose(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", *args], cwd=ROOT, text=True,
        capture_output=True, timeout=240, check=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset-demo-volumes", action="store_true", required=True)
    args = parser.parse_args()
    assert args.reset_demo_volumes
    results = []
    OUTPUT.mkdir(exist_ok=True)
    for cycle in range(1, 4):
        print(f"Cold start {cycle}/3: resetting demo volumes", flush=True)
        down = compose("down", "-v")
        (OUTPUT / f"cold-start-{cycle}-down.log").write_text(
            down.stdout + down.stderr, encoding="utf-8")
        if down.returncode:
            raise RuntimeError(f"Reset failed; inspect cold-start-{cycle}-down.log")
        started = time.monotonic()
        up = compose("up", "-d", "--wait", "--wait-timeout", "180")
        (OUTPUT / f"cold-start-{cycle}-up.log").write_text(
            up.stdout + up.stderr, encoding="utf-8")
        if up.returncode:
            logs = compose("logs", "--tail", "80", "api")
            (OUTPUT / f"cold-start-{cycle}-api.log").write_text(
                logs.stdout + logs.stderr, encoding="utf-8")
            raise RuntimeError(f"Startup failed; inspect cold-start-{cycle}-up.log")
        with httpx.Client(timeout=15) as client:
            client.get("http://localhost:8000/health").raise_for_status()
            login = client.post("http://localhost:8000/v1/auth/login", json={
                "email": "operator@smartops.local", "password": "smartops-demo",
            })
            login.raise_for_status()
            headers = {"Authorization": f"Bearer {login.json()['token']}"}
            bootstrap = client.get("http://localhost:8000/v1/bootstrap", headers=headers)
            bootstrap.raise_for_status()
            data = bootstrap.json()
            assert "cameras" not in data
            assert data["sources"] and data["buildings"]
            assert data["incidents"] == [], "Fresh database must not fabricate incidents"
            assert client.get("http://localhost:8000/v1/cameras", headers=headers).status_code == 404
            with client.stream("GET", "http://localhost:8000/v1/incidents/stream", headers=headers) as stream:
                stream.raise_for_status()
                assert next(stream.iter_lines()) == "event: snapshot"
            client.get("http://localhost:3000/login").raise_for_status()
        row = {"cycle": cycle, "readySeconds": round(time.monotonic() - started, 2),
               "sources": len(data["sources"]), "incidents": len(data["incidents"]),
               "login": "passed", "sseSnapshot": "passed", "frontend": "passed"}
        results.append(row)
        (OUTPUT / "cold-starts.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
