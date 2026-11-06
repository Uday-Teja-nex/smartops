"""Durable bounded reviews after initial incident/evidence delivery, off the capture path."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from threading import Event, Thread

import httpx

from app.outbox import Outbox
from app.log import log


def reserve_budget(connection, day, daily_limit):
    connection.execute('CREATE TABLE IF NOT EXISTS review_budget (day TEXT PRIMARY KEY, used INTEGER NOT NULL)')
    connection.execute('INSERT OR IGNORE INTO review_budget VALUES (?,0)', (day,))
    cursor = connection.execute('UPDATE review_budget SET used=used+1 WHERE day=? AND used<?', (day, daily_limit))
    return cursor.rowcount == 1


def process_one(box, source_id, client, daily_limit=40, budget_path=None, min_interval=0.0):
    """Review the oldest queued incident for this camera.

    min_interval: on constrained hardware, review at most one incident per
    camera per this many seconds; later ones are marked as skipped (with the
    reason) instead of queueing behind the model indefinitely. 0 reviews all.
    """
    import time as _time
    # One source worker owns its jobs. Reserve globally across source processes
    # before network I/O, so failures/restarts cannot evade the daily call cap.
    box.db.execute('BEGIN IMMEDIATE')
    try:
        row = box.db.execute('SELECT id,payload,image FROM review_jobs WHERE source=? AND claimed=0 '
                             'AND id NOT IN (SELECT id FROM pending) '
                             'AND id NOT IN (SELECT id FROM dead_letters) ORDER BY rowid LIMIT 1', (source_id,)).fetchone()
        if row is None:
            box.db.commit()
            return False
        incident_id, raw, image = row
        box.db.execute('CREATE TABLE IF NOT EXISTS review_last (source TEXT PRIMARY KEY, at REAL NOT NULL)')
        last = box.db.execute('SELECT at FROM review_last WHERE source=?', (source_id,)).fetchone()
        now_ts = _time.time()
        if min_interval > 0 and last and now_ts - last[0] < min_interval:
            box.db.execute('DELETE FROM review_jobs WHERE id=?', (incident_id,))
            payload = json.loads(raw)
            notes = [note for note in payload.get('reviewNotes', []) if not note.startswith('AI review')]
            notes.append(f'AI review skipped: this camera was reviewed {int(now_ts - last[0])} s ago '
                         f'(one review per camera every {int(min_interval)} s on this hardware).')
            payload['reviewNotes'] = notes
            box.db.execute('INSERT INTO pending VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                           (incident_id, json.dumps(payload)))
            box.db.commit()
            return True
        box.db.execute('INSERT INTO review_last VALUES (?,?) ON CONFLICT(source) DO UPDATE SET at=excluded.at',
                       (source_id, now_ts))
        day = datetime.now(timezone.utc).date().isoformat()
        if budget_path:
            budget = sqlite3.connect(budget_path)
            try:
                with budget:
                    allowed = reserve_budget(budget, day, daily_limit)
            finally:
                budget.close()
        else:
            allowed = reserve_budget(box.db, day, daily_limit)
        box.db.execute('UPDATE review_jobs SET claimed=1 WHERE id=?', (incident_id,))
        box.db.commit()
    except Exception:
        box.db.rollback()
        raise
    payload = json.loads(raw)
    notes = [note for note in payload.get('reviewNotes', []) if not note.startswith('AI review')]
    try:
        if not allowed:
            raise RuntimeError('daily_limit')
        response = client.post('/v1/incidents/enrich', json={
            'incidentId': incident_id, 'eventType': payload['type'],
            'measuredSummary': payload['shortSummary'], 'imageBase64': image})
        if response.status_code == 503:
            raise EnrichmentUnavailable(_detail(response))
        response.raise_for_status()
        result = response.json()
        for field in ('observations', 'recommendedActions', 'limitations'):
            items = result.get(field)
            if not isinstance(items, list) or len(items) > 4 or any(not isinstance(item, str) or len(item) > 300 for item in items):
                raise ValueError('Invalid enrichment')
        scene, verdict, model = result.get('scene'), result.get('verdict'), result.get('model')
        if not isinstance(scene, str) or not scene or len(scene) > 200 or verdict not in VERDICT_TEXT:
            raise ValueError('Invalid enrichment')
        model = str(model or 'unknown model')[:80]
        seconds = max(int(result.get('latencyMs') or 0), 0) / 1000
        payload['detailedNarrative'] = [scene, *result['observations']]
        payload['recommendedActions'] = result['recommendedActions']
        notes += [f'AI review by {model} ({seconds:.1f} s): {VERDICT_TEXT[verdict]} Rule decision unchanged.']
        notes += result['limitations']
        summary = dict(payload.get('detectionSummary') or {})
        summary['aiReview'] = {'model': model, 'verdict': verdict, 'latencyMs': int(seconds * 1000)}
        payload['detectionSummary'] = summary
    except Exception as exc:
        if not allowed:
            reason = 'daily request cap reached'
        elif isinstance(exc, EnrichmentUnavailable):
            reason = str(exc)
        elif isinstance(exc, httpx.HTTPStatusError):
            reason = f'AI service returned HTTP {exc.response.status_code}'
        elif isinstance(exc, httpx.TimeoutException):
            reason = 'AI service did not answer in time'
        elif isinstance(exc, httpx.TransportError):
            reason = 'AI service unreachable'
        elif isinstance(exc, ValueError):
            reason = 'model output failed validation'
        else:
            reason = f'unexpected error ({type(exc).__name__})'
        notes.append(f'AI review unavailable: {reason}.')
    payload['reviewNotes'] = notes
    with box.db:
        box.db.execute('INSERT INTO pending VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                       (incident_id, json.dumps(payload)))
        box.db.execute('DELETE FROM review_jobs WHERE id=?', (incident_id,))
    return True


VERDICT_TEXT = {
    'consistent': 'image looks consistent with the measured event.',
    'doubtful': 'image casts doubt on the measured event; verify on camera.',
    'unclear': 'image does not show enough to judge.',
}


class EnrichmentUnavailable(Exception):
    pass


def _detail(response):
    try:
        detail = response.json().get('detail')
    except ValueError:
        detail = None
    return detail[:160] if isinstance(detail, str) and detail else f'AI service returned HTTP {response.status_code}'


class IncidentEnrichment:
    def __init__(self, path, source_id):
        self.path, self.source_id = path, source_id
        self.stop = Event()
        self.thread = Thread(target=self.run, name='incident-enrichment', daemon=True)

    def start(self):
        self.thread.start()
        return self

    def close(self):
        self.stop.set()
        self.thread.join(timeout=40)
        if self.thread.is_alive():
            raise RuntimeError('Enrichment did not stop within timeout')

    def run(self):
        box = Outbox(self.path)
        try:
            with box.db:
                box.db.execute('UPDATE review_jobs SET claimed=0 WHERE source=?', (self.source_id,))
            with httpx.Client(base_url=os.getenv('SMARTOPS_ORCHESTRATOR_BASE_URL', 'http://orchestrator:8100'),
                              timeout=float(os.getenv('SMARTOPS_REVIEW_TIMEOUT_SECONDS', '180'))) as client:
                while not self.stop.is_set():
                    try:
                        process_one(box, self.source_id, client,
                                    budget_path=os.getenv('SMARTOPS_REVIEW_BUDGET_PATH', '/data/review-budget.db'),
                                    min_interval=float(os.getenv('SMARTOPS_REVIEW_MIN_INTERVAL_SECONDS', '0')))
                    except Exception as exc:
                        log('enrichment_worker_error', level='error', error=type(exc).__name__)
                    self.stop.wait(.5)
        finally:
            box.close()
