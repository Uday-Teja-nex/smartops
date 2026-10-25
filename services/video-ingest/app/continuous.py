"""Continuous RTSP detection and incident-first rule processing.

One process currently serves one explicitly configured source. No model review
request lies on this path. Rule settings come from source.detectionConfig.zones.
"""
import base64
import os
import signal
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from dataclasses import asdict
from threading import Event

import cv2
import httpx

from app.adapters.rtsp import StreamReader
from app.log import log
from app.rules import RuleEngine, ZoneRule
from app.tracking import Tracker
from app.ring import FrameRing
from app.stream_evidence import upload_evidence
from app.outbox import Outbox


def incident_payload(source, event, captured_at):
    return {
        'id': f'inc-rule-{uuid.uuid4().hex}', 'sourceId': source['id'],
        'buildingId': source['buildingId'], 'floor': source['floor'], 'zone': source['zone'],
        'category': 'Security' if event['type'] in {'restricted_entry', 'after_hours_entry', 'loitering', 'unattended_object'} else 'Safety',
        'subcategory': event['type'], 'type': event['type'], 'severity': 'medium',
        'confidence': event['confidence'], 'status': 'active',
        'startTime': datetime.fromtimestamp(captured_at, UTC).isoformat(),
        'shortSummary': f"{event['type'].replace('_', ' ').capitalize()}: {event['count']} tracked object(s) in {event['zoneId']} for {event['durationSeconds']:.1f}s",
        'detailedNarrative': [], 'recommendedActions': [],
        'reviewNotes': ['AI review pending; enrichment is not yet connected.'],
        'evidence': {'thumbnailUrl': '', 'clipUrl': '', 'restricted': True},
        'modelProvider': 'rule-engine', 'modelVersion': 'zone-rules-v1',
        'detectionSummary': event,
    }


def load_rules(source):
    rules = []
    for zone in source.get('detectionConfig', {}).get('zones', []):
        for rule in zone.get('rules', []):
            rules.append(ZoneRule(zone['id'], zone['polygon'], rule['type'],
                                  rule.get('threshold', 0), rule.get('durationSeconds', 0),
                                  rule.get('radius', .15), rule.get('movementTolerance', .02),
                                  rule.get('timezone', 'UTC'), rule.get('allowedHours', [])))
    return rules


def run(source, client, stop, *, detector_url, fps=3):
    engine = RuleEngine(load_rules(source))
    tracker = Tracker(fps=fps)
    reader = StreamReader(source['sourceUri']).start()
    pending = Outbox(os.getenv('SMARTOPS_OUTBOX_PATH', '/data/incidents.db'))
    pending.recover_evidence()
    ring = FrameRing()
    evidence_waiting = []
    evidence_running = []
    evidence_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='evidence')
    previous_sequence = 0
    last_health = 0
    try:
        while not stop.is_set():
            tick = time.monotonic()
            frame = reader.latest()
            fresh = frame is not None and tick - frame.monotonic_at < 1.5
            try:
                for future, payload in list(evidence_running):
                    if not future.done():
                        continue
                    try:
                        payload['evidence'] = future.result()
                        log('stream_evidence_ready', incidentId=payload['id'])
                    except Exception as exc:
                        payload['reviewNotes'].append(f'Evidence unavailable: {type(exc).__name__}')
                        log('stream_evidence_failed', level='error', incidentId=payload['id'], error=type(exc).__name__)
                    pending.finish_evidence(payload)
                    evidence_running.remove((future, payload))
                for job in list(evidence_waiting):
                    payload, triggered_at, _, _ = job
                    if time.time() - triggered_at > 20:
                        payload['reviewNotes'].append('Evidence unavailable: timed out waiting for post-event footage or encoding capacity')
                        pending.finish_evidence(payload)
                        evidence_waiting.remove(job)
                # Retries use the same incident ID. A full buffer pauses detection
                # rather than silently dropping rule events during API outages.
                if pending:
                    client.post('/v1/incidents', json=pending[0]).raise_for_status()
                    log('rule_incident_persisted', sourceId=source['id'], incidentId=pending[0]['id'])
                    pending.popleft()
                if tick - last_health >= 5:
                    current = client.get(f"/v1/sources/{source['id']}")
                    current.raise_for_status()
                    updated = current.json()
                    if updated['sourceUri'] != source['sourceUri']:
                        # Let the supervisor restart with the new transport URI.
                        break
                    if updated.get('detectionConfig') != source.get('detectionConfig'):
                        engine = RuleEngine(load_rules(updated))
                        tracker = Tracker(fps=fps)
                    source = updated
                    if not source['enabled'] or source['status'] == 'paused':
                        engine = RuleEngine(load_rules(source))
                        tracker = Tracker(fps=fps)
                        last_health = tick
                        stop.wait(1 / fps)
                        continue
                    client.post(f"/v1/sources/{source['id']}/health", json={
                        'status': 'processing' if fresh else 'offline',
                        'adapter': 'continuous-rtsp', 'lastError': None if fresh else reader.last_error,
                        'details': {'frameSequence': reader.sequence, 'pendingIncidents': len(pending)},
                    }).raise_for_status()
                    last_health = tick
                if (source['enabled'] and source['status'] != 'paused'
                        and fresh and frame.sequence != previous_sequence and len(pending) < 100):
                    previous_sequence = frame.sequence
                    image = frame.image
                    if image.shape[1] > 640:
                        image = cv2.resize(image, (640, round(image.shape[0] * 640 / image.shape[1])))
                    ok, encoded = cv2.imencode('.jpg', image)
                    if not ok:
                        raise RuntimeError('Frame encoding failed')
                    jpeg = encoded.tobytes()
                    ring.append(frame.captured_at, jpeg)
                    for job in list(evidence_waiting):
                        payload, triggered_at, snapshot, boxes = job
                        if frame.captured_at >= triggered_at + 5 and not pending and len(evidence_running) < 2:
                            frames = ring.frames(triggered_at - 5, triggered_at + 5)
                            future = evidence_pool.submit(upload_evidence, source['id'], payload['id'], frames, snapshot, boxes)
                            evidence_running.append((future, payload))
                            evidence_waiting.remove(job)
                    response = client.post(detector_url + '/v1/detect', json={
                        'minConfidence': .25,
                        'frames': [{'frameIndex': frame.sequence, 'timestampSeconds': frame.captured_at,
                                    'imageBase64': base64.b64encode(encoded).decode('ascii')}],
                    })
                    response.raise_for_status()
                    # Discard slow detector output instead of treating it as live.
                    if time.monotonic() - frame.monotonic_at < 1.5:
                        observations = tracker.update(response.json()['detections'], frame.monotonic_at)
                        for event in engine.update(frame.monotonic_at, observations, wall_time=frame.captured_at):
                            payload = incident_payload(source, event, frame.captured_at)
                            if len(evidence_waiting) + len(evidence_running) < 20:
                                pending.track_evidence(payload)
                                evidence_waiting.append((payload, frame.captured_at, jpeg, response.json()['detections']))
                            else:
                                payload['reviewNotes'].append('Evidence unavailable: evidence queue capacity reached')
                            pending.append(payload)
                            log('rule_triggered', sourceId=source['id'], incidentId=payload['id'], rule=event)
                        # Persist immediately, before the next frame or any AI work.
                        while pending:
                            client.post('/v1/incidents', json=pending[0]).raise_for_status()
                            log('rule_incident_persisted', sourceId=source['id'], incidentId=pending[0]['id'])
                            pending.popleft()
                        client.post(f"/v1/sources/{source['id']}/observations", json={
                            'sequence': frame.sequence,
                            'capturedAt': datetime.fromtimestamp(frame.captured_at, UTC).isoformat(),
                            'width': image.shape[1], 'height': image.shape[0],
                            'detections': response.json()['detections'],
                            'tracks': [asdict(observation) for observation in observations],
                            'previewJpeg': base64.b64encode(jpeg).decode('ascii'),
                        }).raise_for_status()
            except (httpx.HTTPError, RuntimeError) as exc:
                log('continuous_processing_error', level='error', sourceId=source['id'], error=type(exc).__name__)
            stop.wait(max(0, 1 / fps - (time.monotonic() - tick)))
    finally:
        reader.close()
        evidence_pool.shutdown(wait=True, cancel_futures=True)
        for future, payload in evidence_running:
            try:
                payload['evidence'] = future.result()
            except Exception as exc:
                payload['reviewNotes'].append(f'Evidence unavailable: {type(exc).__name__}')
            pending.finish_evidence(payload)
        for payload, _, _, _ in evidence_waiting:
            payload['reviewNotes'].append('Evidence unavailable: processor stopped before post-event footage completed')
            pending.finish_evidence(payload)
        if pending:
            log('unpersisted_incidents_on_shutdown', level='error', count=len(pending), sourceId=source['id'])
        pending.close()


def main():
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    source_id = os.environ['SMARTOPS_STREAM_SOURCE_ID']
    with httpx.Client(base_url=os.getenv('SMARTOPS_API_BASE_URL', 'http://api:8000'), timeout=5,
                      headers={'X-Internal-Token': os.environ['SMARTOPS_INTERNAL_TOKEN']}) as client:
        response = client.get(f'/v1/sources/{source_id}')
        response.raise_for_status()
        source = response.json()
        if source['sourceType'] != 'rtsp' or not source['enabled'] or source['status'] == 'paused':
            raise RuntimeError('Continuous processor requires an enabled RTSP source')
        run(source, client, stop, detector_url=os.getenv('SMARTOPS_DETECTOR_BASE_URL', 'http://detector:8200'))


if __name__ == '__main__':
    main()
