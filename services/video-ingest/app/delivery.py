"""Deliver durable incidents independently of capture/detection deadlines."""
import os
from threading import Event, Thread

import httpx

from app.log import log
from app.outbox import Outbox


class IncidentDelivery:
    def __init__(self, path, source_id, client_factory=None):
        self.path = path
        self.source_id = source_id
        self.client_factory = client_factory or (lambda: httpx.Client(
            base_url=os.getenv('SMARTOPS_API_BASE_URL', 'http://api:8000'), timeout=5,
            headers={'X-Internal-Token': os.environ['SMARTOPS_INTERNAL_TOKEN']}))
        self.stop = Event()
        self.thread = Thread(target=self.run, name='incident-delivery', daemon=True)

    def start(self):
        self.thread.start()
        return self

    def close(self):
        self.stop.set()
        self.thread.join(timeout=10)
        if self.thread.is_alive():
            raise RuntimeError('Incident delivery did not stop within timeout')

    def run(self):
        box = Outbox(self.path)
        delay = .5
        try:
            with self.client_factory() as client:
                while not self.stop.is_set():
                    if not box:
                        self.stop.wait(.05)
                        continue
                    payload = box[0]
                    try:
                        client.post('/v1/incidents', json=payload).raise_for_status()
                        box.acknowledge(payload)
                        delay = .5
                        log('rule_incident_persisted', sourceId=self.source_id, incidentId=payload['id'])
                    except httpx.HTTPError as exc:
                        log('incident_delivery_failed', level='error', sourceId=self.source_id,
                            incidentId=payload['id'], error=type(exc).__name__)
                        self.stop.wait(delay)
                        delay = min(5, delay * 2)
        finally:
            box.close()
