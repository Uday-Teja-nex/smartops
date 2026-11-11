"""Demo history builder: `python -m app.history [--days 3] [--sessions 3]`.

Runs the real pipeline (detector, tracker, zone rules, evidence encoder,
incident API) over each camera's recorded clip, as fast as the detector
allows, with frames stamped at virtual times during business hours on each
of the last N days. Nothing here is hand-written: every incident is a rule
firing on real detections. Incidents are created with `replay: true`, so
the API stamps them at their own time, marks them as history and never
notifies anyone. Operator actions on them are scripted, and the audit trail
says so (`Scripted demo action`). `demo.ps1 build-history` then exports the
result as the snapshot every `reset` restores.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import cv2
import httpx

from app.continuous import evidence_failure, incident_payload, load_rules, raw_observations
from app.overlays import annotate
from app.ring import FrameRing
from app.rules import RuleEngine
from app.stream_evidence import upload_evidence
from app.tracking import Tracker

HISTORY_NOTES = ['Demo history: recorded footage replayed through the detection pipeline.',
                 'AI review skipped: demo history is not sent to the AI model.']
SESSION_SECONDS = 120  # each replay session loops the clip for about two minutes, as the live stream does


def clip_frames(path: Path, fps: int, seconds: float, lead_in: float = 6.0):
    """Yield (offset_seconds, image) at `fps`, looping the clip for `seconds`.

    Like the live stream, a session joins the loop part-way: it starts
    `lead_in` seconds before the clip's end, so an event at the loop point
    has its pre-event footage instead of none."""
    capture = cv2.VideoCapture(str(path))
    native = capture.get(cv2.CAP_PROP_FPS) or 25.0
    frames = capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    capture.release()
    duration = frames / native if frames else 0
    if duration <= 0:
        raise ValueError(f'Unreadable clip: {path.name}')
    step = max(1, round(native / fps))
    lead_in = min(lead_in, duration)
    skip = duration - lead_in  # play only the clip's tail on the first pass
    for loop in range(max(1, math.ceil(seconds / duration)) + 1):
        capture = cv2.VideoCapture(str(path))
        index = 0
        try:
            while True:
                ok, image = capture.read()
                if not ok or image is None:
                    break
                at = loop * duration + index / native - skip
                if index % step == 0 and at >= 0:
                    yield at, image
                index += 1
        finally:
            capture.release()


def scripted_actions(rng: random.Random, start: datetime) -> list[dict]:
    """A plausible operator response, chosen deterministically per incident."""
    minutes = lambda low, high: start + timedelta(seconds=rng.uniform(low * 60, high * 60))  # noqa: E731
    roll = rng.random()
    if roll < 0.7:
        return [{'action': 'acknowledge', 'at': minutes(1, 4)}, {'action': 'resolve', 'at': minutes(6, 30)}]
    if roll < 0.9:
        return [{'action': 'acknowledge', 'at': minutes(1, 3)},
                {'action': 'false_positive', 'at': minutes(3, 8), 'note': 'Checked on camera; no action needed'}]
    return [{'action': 'assign', 'at': minutes(1, 3), 'assignee': 'Security team'},
            {'action': 'resolve', 'at': minutes(10, 45)}]


class Replayer:
    def __init__(self, client: httpx.Client, detector_url: str, fps: int, built_at: datetime, seed: int):
        self.client, self.detector_url, self.fps = client, detector_url, fps
        self.built_at = built_at
        self.rng = random.Random(seed)
        self.stats = {'incidents': 0, 'evidence': 0, 'evidenceFailed': 0, 'frames': 0}

    def detect(self, encoded: bytes, offset: float) -> list[dict]:
        import base64

        response = self.client.post(self.detector_url + '/v1/detect', json={
            'minConfidence': .25,
            'frames': [{'frameIndex': 0, 'timestampSeconds': offset,
                        'imageBase64': base64.b64encode(encoded).decode('ascii')}]})
        response.raise_for_status()
        return response.json()['detections']

    def post(self, payload: dict) -> None:
        self.client.post('/v1/incidents', json=payload).raise_for_status()

    def finish(self, source: dict, job: dict, ring: FrameRing) -> None:
        payload, triggered = job['payload'], job['t']
        self.post(payload)
        self.stats['incidents'] += 1
        frames = ring.frames(triggered - 5, triggered + 5)
        try:
            payload['evidence'] = upload_evidence(source['id'], payload['id'], frames, job['snapshot'],
                                                  job['boxes'], triggered, job['pre_seconds'])
            self.stats['evidence'] += 1
        except Exception as exc:  # noqa: BLE001 - the incident stands without a clip, saying why
            payload['reviewNotes'].append(f'Evidence unavailable: {evidence_failure(exc)}')
            self.stats['evidenceFailed'] += 1
        self.post(payload)
        start = datetime.fromtimestamp(triggered, UTC)
        for action in scripted_actions(self.rng, start):
            body = {**action, 'at': action['at'].isoformat()}
            self.client.post(f"/v1/incidents/{payload['id']}/replay-action", json=body).raise_for_status()

    def session(self, source: dict, clip: Path, started: datetime) -> None:
        engine, tracker = RuleEngine(load_rules(source)), Tracker(fps=self.fps)
        ring = FrameRing(seconds=40)
        base = started.timestamp()
        waiting: list[dict] = []
        for offset, image in clip_frames(clip, self.fps, SESSION_SECONDS):
            t = base + offset
            if image.shape[1] > 640:  # what the live loop sends the detector
                image = cv2.resize(image, (640, round(image.shape[0] * 640 / image.shape[1])))
            ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                continue
            detections = self.detect(encoded.tobytes(), offset)
            self.stats['frames'] += 1
            ok, annotated = cv2.imencode('.jpg', annotate(image, detections), [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                continue
            ring.append(t, annotated.tobytes())
            observations = tracker.update(detections, t)
            for event in engine.update(t, observations, wall_time=t, counted=raw_observations(detections)):
                payload = incident_payload(source, event, t)
                payload['replay'] = True
                payload['reviewNotes'] = list(HISTORY_NOTES)
                payload['detectionSummary'] = {**payload['detectionSummary'], 'historyReplay': {
                    'builtAt': self.built_at.isoformat(), 'clip': clip.name, 'session': started.isoformat()}}
                waiting.append({'payload': payload, 't': t, 'snapshot': annotated.tobytes(), 'boxes': detections,
                                'pre_seconds': min(5.0, offset)})
            for job in [job for job in waiting if t >= job['t'] + 5]:
                waiting.remove(job)
                self.finish(source, job, ring)
        for job in waiting:  # fired in the clip's last seconds: no full post-roll
            self.finish(source, job, ring)


def session_starts(days: int, sessions: int, tz: ZoneInfo, now: datetime, rng: random.Random) -> list[datetime]:
    """Business-hours start times (09:00-19:00 local) on each of the last `days` days."""
    starts = []
    today = now.astimezone(tz).date()
    for back in range(days, 0, -1):
        day = today - timedelta(days=back)
        for slot in range(sessions):
            span = 10 * 60 / sessions  # minutes per slot between 09:00 and 19:00
            minute = rng.uniform(slot * span, (slot + 1) * span - SESSION_SECONDS / 60)
            local = datetime(day.year, day.month, day.day, 9, tzinfo=tz) + timedelta(minutes=minute)
            starts.append(local.astimezone(UTC))
    return starts


def clips_by_path(manifest_path: Path, input_root: Path) -> dict[str, Path]:
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    return {item['path']: input_root / item['file'] for item in manifest['streams']
            if (input_root / item['file']).exists()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--days', type=int, default=3)
    parser.add_argument('--sessions', type=int, default=3, help='replay sessions per camera per day')
    parser.add_argument('--seed', type=int, default=20261111)
    args = parser.parse_args()
    if not 1 <= args.days <= 14 or not 1 <= args.sessions <= 8:
        parser.error('--days must be 1-14 and --sessions 1-8')
    root = Path(os.getenv('SMARTOPS_SAMPLE_DATA', '/app/sample-data'))
    clips = clips_by_path(root / 'streams.json', root / 'input')
    tz = ZoneInfo(os.getenv('SMARTOPS_HISTORY_TIMEZONE', 'Asia/Kolkata'))
    fps = int(os.getenv('SMARTOPS_STREAM_FPS', '3'))
    built_at = datetime.now(UTC)
    with httpx.Client(base_url=os.getenv('SMARTOPS_API_BASE_URL', 'http://api:8000'), timeout=30,
                      headers={'X-Internal-Token': os.environ['SMARTOPS_INTERNAL_TOKEN']}) as client:
        response = client.get('/v1/sources')
        response.raise_for_status()
        replayer = Replayer(client, os.getenv('SMARTOPS_DETECTOR_BASE_URL', 'http://detector:8200'), fps,
                            built_at, args.seed)
        cameras = []
        for source in response.json():
            path = source['sourceUri'].rstrip('/').rsplit('/', 1)[-1]
            if source['sourceType'] == 'rtsp' and source['enabled'] and path in clips:
                cameras.append((source, clips[path]))
        if not cameras:
            print('No enabled cameras with recorded footage; nothing to replay')
            return 1
        starts = session_starts(args.days, args.sessions, tz, built_at, random.Random(args.seed))
        for number, started in enumerate(starts, 1):
            for source, clip in cameras:
                replayer.session(source, clip, started)
            print(f'session {number}/{len(starts)} ({started.astimezone(tz):%a %H:%M}): {replayer.stats}', flush=True)
    print(json.dumps({'builtAt': built_at.isoformat(), 'days': args.days, 'sessionsPerDay': args.sessions,
                      'cameras': [source['id'] for source, _ in cameras], **replayer.stats}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
