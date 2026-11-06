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
from app.frame_health import FrameHealth
from app.delivery import IncidentDelivery
from app.overlays import annotate
from app.enrichment import IncidentEnrichment


# rule type -> (incident category, severity, plain-English summary template)
RULE_PRESENTATION = {
    'crowding': ('Queue & Crowd', 'medium', '{count} people in {zone} for {seconds}s (crowding limit exceeded)'),
    'queue_build_up': ('Queue & Crowd', 'low', '{count} people queuing in {zone} for {seconds}s'),
    'restricted_entry': ('Security', 'high', 'Person entered restricted zone {zone}'),
    'after_hours_entry': ('Security', 'high', 'Person in {zone} outside permitted hours'),
    'loitering': ('Security', 'low', 'Person stayed in {zone} for {seconds}s'),
    'unattended_object': ('Security', 'high', 'Bag left unattended in {zone} for {seconds}s'),
    'blocked_exit': ('Safety', 'high', 'Exit zone {zone} obstructed for {seconds}s'),
}


def describe_event(event):
    template = RULE_PRESENTATION[event['type']][2]
    return template.format(count=event['count'], zone=event['zoneId'], seconds=round(event['durationSeconds']))


def incident_payload(source, event, captured_at):
    return {
        'id': f'inc-rule-{uuid.uuid4().hex}', 'sourceId': source['id'],
        # The drawn zone ("Checkout queue") is what operators and per-zone analytics need;
        # the camera's own area stays on the camera record.
        'buildingId': source['buildingId'], 'floor': source['floor'], 'zone': event['zoneId'],
        'category': RULE_PRESENTATION[event['type']][0],
        'subcategory': event['type'], 'type': event['type'], 'severity': RULE_PRESENTATION[event['type']][1],
        'confidence': event['confidence'], 'status': 'active',
        'startTime': datetime.fromtimestamp(captured_at, UTC).isoformat(),
        'shortSummary': describe_event(event),
        'detailedNarrative': [], 'recommendedActions': [],
        'reviewNotes': ['AI review unavailable: enrichment is not configured.'],
        'evidence': {'thumbnailUrl': '', 'clipUrl': '', 'restricted': True},
        'modelProvider': 'rule-engine', 'modelVersion': 'zone-rules-v1',
        'detectionSummary': event,
    }


DEFAULT_AGGREGATE_COOLDOWN = 120.0
# Vision-encoder cost grows with pixels: on the laptop CPU a 384 px frame
# reviews in about 11 s versus about 24 s at 640 px
# (docs/verification/vlm-image-size-benchmark.json).
REVIEW_WIDTH = int(os.getenv('SMARTOPS_REVIEW_IMAGE_WIDTH', '384'))


def review_jpeg(image):
    if image.shape[1] > REVIEW_WIDTH:
        image = cv2.resize(image, (REVIEW_WIDTH, round(image.shape[0] * REVIEW_WIDTH / image.shape[1])),
                           interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise RuntimeError('Review image encoding failed')
    return base64.b64encode(encoded).decode('ascii')


def load_rules(source):
    rules = []
    for zone in source.get('detectionConfig', {}).get('zones', []):
        for rule in zone.get('rules', []):
            rules.append(ZoneRule(zone['id'], zone['polygon'], rule['type'],
                                  rule.get('threshold', 0), rule.get('durationSeconds', 0),
                                  rule.get('radius', .15), rule.get('movementTolerance', .02),
                                  rule.get('timezone', 'UTC'), rule.get('allowedHours', []),
                                  rule.get('cooldownSeconds', DEFAULT_AGGREGATE_COOLDOWN
                                           if rule['type'] in {'crowding', 'queue_build_up'} else 0)))
    return rules


def run(source, client, stop, *, detector_url, fps=3):
    engine = RuleEngine(load_rules(source))
    tracker = Tracker(fps=fps)
    reader = StreamReader(source['sourceUri']).start()
    outbox_path = os.getenv('SMARTOPS_OUTBOX_PATH', '/data/incidents.db')
    pending = Outbox(outbox_path)
    pending.recover_evidence()
    delivery = IncidentDelivery(outbox_path, source['id']).start()
    enrichment = (IncidentEnrichment(outbox_path, source['id']).start()
                  if os.getenv('SMARTOPS_STREAM_ENRICHMENT', 'false').lower() == 'true' else None)
    ring = FrameRing()
    evidence_waiting = []
    evidence_running = []
    evidence_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='evidence')
    previous_sequence = 0
    last_health = time.monotonic() - 5
    processed_frames = 0
    last_processed_frames = 0
    detector_ms = None
    processing_lag_ms = None
    errors = 0
    frame_health = FrameHealth()
    reported_issues = []
    try:
        while not stop.is_set():
            if not delivery.thread.is_alive():
                raise RuntimeError('Incident delivery stopped unexpectedly')
            if enrichment and not enrichment.thread.is_alive():
                raise RuntimeError('Incident enrichment stopped unexpectedly')
            tick = time.monotonic()
            frame = reader.latest()
            fresh = frame is not None and tick - frame.monotonic_at < 1.5
            quality = frame_health.update(tick, frame.image if fresh else None)
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
                if tick - last_health >= 5 or quality['issues'] != reported_issues:
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
                        'status': ('offline' if 'camera_offline' in quality['issues'] else
                                   'failing' if quality['issues'] else 'processing' if fresh else 'offline'),
                        'adapter': 'continuous-rtsp',
                        'lastError': ', '.join(quality['issues']) if quality['issues'] else None if fresh else reader.last_error,
                        'details': {'frameSequence': reader.sequence, **pending.delivery_health(),
                                    'processedFrames': processed_frames,
                                    'processingFps': (processed_frames - last_processed_frames) / max(.001, tick - last_health),
                                    'detectorLatencyMs': detector_ms, 'processingLagMs': processing_lag_ms,
                                    'processingErrors': errors,
                                    'pendingEvidence': len(evidence_waiting) + len(evidence_running),
                                    'warmingUp': not fresh and not quality['issues'], **quality},
                    }).raise_for_status()
                    reported_issues = quality['issues']
                    last_processed_frames = processed_frames
                    last_health = tick
                if (source['enabled'] and source['status'] != 'paused'
                        and fresh and frame.sequence != previous_sequence and len(pending) < 100):
                    previous_sequence = frame.sequence
                    image = frame.image
                    if image.shape[1] > 640:
                        image = cv2.resize(image, (640, round(image.shape[0] * 640 / image.shape[1])))
                    ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if not ok:
                        raise RuntimeError('Frame encoding failed')
                    jpeg = encoded.tobytes()
                    for job in list(evidence_waiting):
                        payload, triggered_at, snapshot, boxes = job
                        if frame.captured_at >= triggered_at + 5 and not pending and len(evidence_running) < 2:
                            frames = ring.frames(triggered_at - 5, triggered_at + 5)
                            future = evidence_pool.submit(upload_evidence, source['id'], payload['id'], frames, snapshot, boxes, triggered_at)
                            evidence_running.append((future, payload))
                            evidence_waiting.remove(job)
                    response = client.post(detector_url + '/v1/detect', json={
                        'minConfidence': .25,
                        'frames': [{'frameIndex': frame.sequence, 'timestampSeconds': frame.captured_at,
                                    'imageBase64': base64.b64encode(encoded).decode('ascii')}],
                    })
                    response.raise_for_status()
                    detector_ms = response.json().get('inferenceMs')
                    processing_lag_ms = (time.monotonic() - frame.monotonic_at) * 1000
                    # Discard slow detector output instead of treating it as live.
                    if time.monotonic() - frame.monotonic_at < 1.5:
                        processed_frames += 1
                        annotated = annotate(image, response.json()['detections'])
                        ok, evidence_encoded = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        if not ok:
                            raise RuntimeError('Evidence annotation encoding failed')
                        evidence_jpeg = evidence_encoded.tobytes()
                        ring.append(frame.captured_at, evidence_jpeg)
                        observations = tracker.update(response.json()['detections'], frame.monotonic_at)
                        for event in engine.update(frame.monotonic_at, observations, wall_time=frame.captured_at):
                            payload = incident_payload(source, event, frame.captured_at)
                            if len(evidence_waiting) + len(evidence_running) < 20:
                                # The AI reviews the clean frame; burned-in boxes and scores confuse it.
                                pending.track_evidence(payload, review_jpeg(image) if enrichment else None)
                                evidence_waiting.append((payload, frame.captured_at, evidence_jpeg, response.json()['detections']))
                            else:
                                payload['reviewNotes'].append('Evidence unavailable: evidence queue capacity reached')
                            pending.append(payload)
                            log('rule_triggered', sourceId=source['id'], incidentId=payload['id'], rule=event)
                        # Durable delivery runs concurrently; evidence waits until
                        # initial incident persistence has drained the outbox.
                        client.post(f"/v1/sources/{source['id']}/observations", json={
                            'sequence': frame.sequence,
                            'capturedAt': datetime.fromtimestamp(frame.captured_at, UTC).isoformat(),
                            'width': image.shape[1], 'height': image.shape[0],
                            'detections': response.json()['detections'],
                            'tracks': [asdict(observation) for observation in observations],
                            'previewJpeg': base64.b64encode(jpeg).decode('ascii'),
                        }).raise_for_status()
            except (httpx.HTTPError, RuntimeError) as exc:
                errors += 1
                log('continuous_processing_error', level='error', sourceId=source['id'], error=type(exc).__name__)
            stop.wait(max(0, 1 / fps - (time.monotonic() - tick)))
    finally:
        if enrichment:
            enrichment.close()
        delivery.close()
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
        fps = int(os.getenv('SMARTOPS_STREAM_FPS', '3'))
        if not 2 <= fps <= 5:
            raise ValueError('SMARTOPS_STREAM_FPS must be between 2 and 5')
        run(source, client, stop, detector_url=os.getenv('SMARTOPS_DETECTOR_BASE_URL', 'http://detector:8200'), fps=fps)


if __name__ == '__main__':
    main()
