"""Bounded source workers with independent decoder, tracker and delivery state."""
import hashlib
import os
import signal
import subprocess
import sys
import time
from threading import Event

import httpx

from app.log import log


class Supervisor:
    def __init__(self, launch, capacity=3):
        self.launch = launch
        self.capacity = capacity
        self.workers = {}
        self.stopping = {}
        self.retry_at = {}

    def reconcile(self, sources, now):
        desired = {s['id'] for s in sources if s['sourceType'] == 'rtsp'
                   and s['enabled'] and s['status'] != 'paused'}
        for source_id, process in list(self.workers.items()):
            code = process.poll()
            if code is not None:
                self.workers.pop(source_id)
                self.stopping.pop(source_id, None)
                self.retry_at[source_id] = now + 5
                log('stream_worker_exited', sourceId=source_id, exitCode=code)
            elif source_id not in desired and source_id not in self.stopping:
                process.terminate()
                self.stopping[source_id] = now
            elif source_id in self.stopping and now - self.stopping[source_id] >= 30:
                process.kill()
        self.retry_at = {id: at for id, at in self.retry_at.items() if id in desired}
        for source_id in sorted(desired):
            if len(self.workers) >= self.capacity:
                break
            if source_id not in self.workers and now >= self.retry_at.get(source_id, 0):
                self.workers[source_id] = self.launch(source_id)
                log('stream_worker_started', sourceId=source_id)


def launch_worker(source_id):
    environment = os.environ.copy()
    environment['SMARTOPS_STREAM_SOURCE_ID'] = source_id
    # IDs are API data, never filesystem paths. Each source owns its journal.
    digest = hashlib.sha256(source_id.encode()).hexdigest()
    environment['SMARTOPS_OUTBOX_PATH'] = f'/data/{digest}.db'
    return subprocess.Popen([sys.executable, '-m', 'app.continuous'], env=environment)


def main():
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    capacity = int(os.getenv('SMARTOPS_MAX_STREAMS', '3'))
    if not 1 <= capacity <= 16:
        raise ValueError('SMARTOPS_MAX_STREAMS must be between 1 and 16')
    manager = Supervisor(launch_worker, capacity)
    selected = {value.strip() for value in os.getenv('SMARTOPS_STREAM_SOURCE_IDS', '').split(',') if value.strip()}
    with httpx.Client(base_url=os.getenv('SMARTOPS_API_BASE_URL', 'http://api:8000'), timeout=5,
                      headers={'X-Internal-Token': os.environ['SMARTOPS_INTERNAL_TOKEN']}) as client:
        try:
            while not stop.is_set():
                try:
                    response = client.get('/v1/sources', params={'sourceType': 'rtsp', 'enabled': 'true'})
                    response.raise_for_status()
                    sources = response.json()
                    if selected:
                        sources = [source for source in sources if source['id'] in selected]
                    manager.reconcile(sources, time.monotonic())
                except httpx.HTTPError as exc:
                    # Keep current workers through API outages; their outboxes retry.
                    log('stream_discovery_failed', level='error', error=type(exc).__name__)
                stop.wait(2)
        finally:
            while manager.workers:
                manager.reconcile([], time.monotonic())
                time.sleep(.1)


if __name__ == '__main__':
    main()
