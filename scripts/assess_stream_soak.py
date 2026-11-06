"""Pass/fail verdict for a stream soak recorded by verify_stream_soak.py.

Usage: python scripts/assess_stream_soak.py <soak.json> [<assessment.json>]

Criteria (Phase 2 gate), after a 2-minute warm-up:
  - every sample: each stream processes >= 2.0 fps and its latest observation
    is < 5 s old (no stalls), with no request errors;
  - memory: each SmartOps container's median in the last 5 minutes is within
    10 % (or 25 MiB) of its median in the first 5 minutes after warm-up.
"""
import json
import statistics
import sys

UNITS = {"KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "B": 1 / 1024 / 1024}


def mib(text: str) -> float:
    value = text.split("/")[0].strip()
    for unit, factor in UNITS.items():
        if value.endswith(unit):
            return float(value[: -len(unit)]) * factor
    return float(value)


def main() -> int:
    report = json.load(open(sys.argv[1], encoding="utf-8"))
    samples = [s for s in report["samples"] if s["elapsedSeconds"] >= 120]
    failures: list[str] = []
    fps: dict[str, list[float]] = {}
    for sample in samples:
        for source in sample["sources"]:
            sid = source["id"]
            if source.get("error"):
                failures.append(f"{sample['elapsedSeconds']}s {sid}: request error {source['error']}")
                continue
            rate = (source.get("health") or {}).get("processingFps")
            age = source.get("observationAgeSeconds")
            fps.setdefault(sid, []).append(rate or 0.0)
            if rate is None or rate < 2.0:
                failures.append(f"{sample['elapsedSeconds']}s {sid}: {rate} fps")
            if age is None or age >= 5:
                failures.append(f"{sample['elapsedSeconds']}s {sid}: observation {age} s old")
    memory: dict[str, dict[str, float]] = {}
    if samples:
        start, end = samples[0]["elapsedSeconds"], samples[-1]["elapsedSeconds"]
        early = [s for s in samples if s["elapsedSeconds"] <= start + 300]
        late = [s for s in samples if s["elapsedSeconds"] >= end - 300]
        names = {row["Name"] for s in samples for row in s.get("containers", [])}
        for name in sorted(names):
            first = [mib(r["MemUsage"]) for s in early for r in s.get("containers", []) if r["Name"] == name]
            last = [mib(r["MemUsage"]) for s in late for r in s.get("containers", []) if r["Name"] == name]
            if not first or not last:
                continue
            a, b = statistics.median(first), statistics.median(last)
            memory[name] = {"firstMiB": round(a, 1), "lastMiB": round(b, 1), "growthMiB": round(b - a, 1)}
            if b - a > max(25.0, 0.10 * a):
                failures.append(f"{name}: memory grew {a:.0f} -> {b:.0f} MiB")
    minutes = report.get("elapsedSeconds", 0) / 60
    if minutes < report.get("requestedMinutes", 30) - 0.5:
        failures.append(f"run lasted {minutes:.1f} of {report.get('requestedMinutes')} minutes")
    verdict = {
        "passed": not failures,
        "minutes": round(minutes, 1),
        "samplesAfterWarmup": len(samples),
        "fps": {sid: {"min": round(min(v), 2), "median": round(statistics.median(v), 2)} for sid, v in fps.items()},
        "memory": memory,
        "failures": failures[:50],
        "failureCount": len(failures),
    }
    text = json.dumps(verdict, indent=2)
    if len(sys.argv) > 2:
        open(sys.argv[2], "w", encoding="utf-8").write(text)
    print(text)
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
