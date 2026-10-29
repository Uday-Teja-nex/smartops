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


def process_one(box, source_id, client, daily_limit=40, budget_path=None):
    # One source worker owns its jobs. Reserve globally across source processes
    # before network I/O, so failures/restarts cannot evade the daily call cap.
    box.db.execute('BEGIN IMMEDIATE')
    try:
        row = box.db.execute('SELECT id,payload,image FROM review_jobs WHERE source=? AND claimed=0 '
                             'AND id NOT IN (SELECT id FROM pending) ORDER BY rowid LIMIT 1', (source_id,)).fetchone()
        if row is None:
            box.db.commit()
            return False
        incident_id, raw, image = row
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
        response.raise_for_status()
        result = response.json()
        for field in ('observations', 'recommendedActions', 'limitations'):
            items = result.get(field)
            if not isinstance(items, list) or len(items) > 4 or any(not isinstance(item, str) or len(item) > 300 for item in items):
                raise ValueError('Invalid enrichment')
        payload['detailedNarrative'] = result['observations']
        payload['recommendedActions'] = result['recommendedActions']
        notes += ['AI review completed: supplemental image observations; rule decision unchanged.']
        notes += result['limitations']
    except Exception as exc:
        notes.append('AI review unavailable: daily request cap reached.' if not allowed
                     else 'AI review unavailable: ' + type(exc).__name__ + '.')
    payload['reviewNotes'] = notes
    with box.db:
        box.db.execute('INSERT INTO pending VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                       (incident_id, json.dumps(payload)))
        box.db.execute('DELETE FROM review_jobs WHERE id=?', (incident_id,))
    return True


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
            with httpx.Client(base_url=os.getenv('SMARTOPS_ORCHESTRATOR_BASE_URL', 'http://orchestrator:8100'), timeout=35) as client:
                while not self.stop.is_set():
                    try:
                        process_one(box, self.source_id, client,
                                    budget_path=os.getenv('SMARTOPS_REVIEW_BUDGET_PATH', '/data/review-budget.db'))
                    except Exception as exc:
                        log('enrichment_worker_error', level='error', error=type(exc).__name__)
                    self.stop.wait(.5)
        finally:
            box.close()
