"""Demo history replays real footage through the rules at virtual past times."""
import json
import random
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import cv2
import httpx
import numpy as np

from app import history

SOURCE = {
    'id': 'src-test', 'buildingId': 'bldg-1', 'floor': 'L1',
    'detectionConfig': {'zones': [{'id': 'Atrium floor', 'polygon': [[0, 0], [0.5, 0], [0.5, 1], [0, 1]],
                                   'rules': [{'type': 'crowding', 'threshold': 2, 'durationSeconds': 2}]}]},
}


def write_clip(path, seconds=20, fps=10):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), fps, (320, 240))
    for index in range(seconds * fps):
        frame = np.full((240, 320, 3), index % 255, dtype=np.uint8)
        writer.write(frame)
    writer.release()


def person(x):
    return {'label': 'person', 'confidence': .9, 'bbox': {'x': x, 'y': .2, 'w': .05, 'h': .3}}


def fake_client(log):
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/v1/detect':
            return httpx.Response(200, json={'detections': [person(.1), person(.2), person(.3)]})
        body = json.loads(request.content)
        log.append((request.url.path, body))
        return httpx.Response(201 if request.url.path == '/v1/incidents' else 200, json={})
    return httpx.Client(base_url='http://api', transport=httpx.MockTransport(handle))


def test_clip_frames_samples_at_fps_and_loops_to_the_session_length(tmp_path):
    clip = tmp_path / 'clip.mp4'
    write_clip(clip, seconds=10)
    offsets = [offset for offset, _ in history.clip_frames(clip, 3, 25, lead_in=6)]
    assert 0 <= offsets[0] < .5 and offsets[-1] > 25  # a 6 s lead-in plus three loops cover 25 s
    gaps = [b - a for a, b in zip(offsets, offsets[1:])]
    assert max(gaps) < 0.5 and min(gaps) > 0  # continuous across loop boundaries


def test_replayed_incidents_are_marked_stamped_in_the_past_and_scripted(tmp_path, monkeypatch):
    clip = tmp_path / 'clip.mp4'
    write_clip(clip)
    uploads = []

    def fake_upload(source_id, incident_id, frames, snapshot, boxes, triggered_at, pre_seconds):
        uploads.append((frames, triggered_at, pre_seconds))
        return {'thumbnailUrl': '/v1/evidence/s/url', 'clipUrl': '/v1/evidence/c/url', 'restricted': True}

    monkeypatch.setattr(history, 'upload_evidence', fake_upload)
    monkeypatch.setattr(history, 'SESSION_SECONDS', 20)
    log = []
    started = datetime(2026, 11, 9, 4, 30, tzinfo=UTC)
    replayer = history.Replayer(fake_client(log), 'http://detector', 3, datetime(2026, 11, 11, tzinfo=UTC), seed=1)
    replayer.session(SOURCE, clip, started)

    created = [body for path, body in log if path == '/v1/incidents']
    assert created, 'the crowding rule should fire on three people in the zone'
    for body in created:
        assert body['replay'] is True
        assert body['detectionSummary']['historyReplay']['session'] == started.isoformat()
        assert body['reviewNotes'][0].startswith('Demo history:')
        assert datetime.fromisoformat(body['startTime']) >= started
    # Created first, then updated with its evidence links.
    assert created[1]['evidence']['clipUrl'] == '/v1/evidence/c/url'
    for frames, triggered, pre in uploads:
        # Pre-roll is whatever the session had before the event, at most 5 s.
        assert abs(pre - min(5.0, triggered - started.timestamp())) < 1e-3
        assert frames[0][0] <= triggered - pre + .75 and frames[-1][0] >= triggered + 4

    actions = [(path, body) for path, body in log if path.endswith('/replay-action')]
    assert actions and all(path == f"/v1/incidents/{created[0]['id']}/replay-action" for path, _ in actions[:2])
    start = datetime.fromisoformat(created[0]['startTime'])
    assert all(datetime.fromisoformat(body['at']) > start for _, body in actions[:2])
    assert replayer.stats['incidents'] == len(created) // 2


def test_sessions_fall_in_local_business_hours_on_past_days():
    tz = ZoneInfo('Asia/Kolkata')
    now = datetime(2026, 11, 11, 6, tzinfo=UTC)
    starts = history.session_starts(3, 3, tz, now, random.Random(1))
    assert len(starts) == 9
    for start in starts:
        local = start.astimezone(tz)
        assert 9 <= local.hour < 19 and local.date() < now.astimezone(tz).date()
        assert local.date() >= (now.astimezone(tz) - timedelta(days=3)).date()


def test_scripted_actions_follow_the_incident_in_order():
    rng = random.Random(7)
    start = datetime(2026, 11, 9, 10, tzinfo=UTC)
    for _ in range(50):
        actions = history.scripted_actions(rng, start)
        times = [action['at'] for action in actions]
        assert times == sorted(times) and times[0] > start
        assert actions[-1]['action'] in {'resolve', 'false_positive'}


def test_an_event_at_the_loop_point_gets_pre_event_footage(tmp_path):
    clip = tmp_path / 'clip.mp4'
    write_clip(clip, seconds=10)
    offsets = [offset for offset, _ in history.clip_frames(clip, 3, 20, lead_in=6)]
    # The clip restarts 6 s into the session, so 5 s of footage precede it.
    restart = 6.0
    assert any(abs(offset - restart) < .2 for offset in offsets)
    assert offsets[0] <= restart - 5
