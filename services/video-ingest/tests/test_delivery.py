from threading import Event
import time

import httpx

from app.delivery import IncidentDelivery
from app.outbox import Outbox


def test_rejected_incident_does_not_block_later_delivery(tmp_path):
    import json
    path = tmp_path / 'rejected.db'
    box = Outbox(path)
    box.append({'id': 'bad'})
    box.append({'id': 'good'})
    delivered = Event()
    def handle(request):
        if json.loads(request.content)['id'] == 'bad':
            return httpx.Response(422)
        delivered.set()
        return httpx.Response(201)
    delivery = IncidentDelivery(path, 'source', client_factory=lambda: httpx.Client(
        base_url='http://test', transport=httpx.MockTransport(handle))).start()
    try:
        assert delivered.wait(3)
        assert box.db.execute('SELECT id,status FROM dead_letters').fetchall() == [('bad', 422)]
    finally:
        delivery.close()
        box.close()


def test_delivery_retries_without_blocking_producer_and_survives_new_update(tmp_path):
    path = tmp_path / 'delivery.db'
    outbox = Outbox(path)
    outbox.append({'id': 'one', 'version': 1})
    delivered = Event()
    calls = []
    def handle(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        delivered.set()
        return httpx.Response(201)
    delivery = IncidentDelivery(path, 'source', client_factory=lambda: httpx.Client(
        base_url='http://test', transport=httpx.MockTransport(handle))).start()
    try:
        assert delivered.wait(3)
        deadline = time.monotonic() + 1
        while outbox and time.monotonic() < deadline:
            time.sleep(.01)
        assert not outbox
        assert len(calls) == 2
    finally:
        delivery.close()
        outbox.close()
