import httpx
from app.outbox import Outbox
from app.enrichment import process_one


def seed(box, identifier='one'):
    payload = {'id': identifier, 'sourceId': 'camera', 'type': 'restricted_entry',
               'shortSummary': 'Measured zone entry', 'severity': 'medium', 'confidence': .8,
               'status': 'active', 'modelProvider': 'rule-engine', 'reviewNotes': []}
    box.track_evidence(payload, 'aA==')
    payload['evidence'] = {'clipUrl': '/recorded'}
    box.finish_evidence(payload)
    return payload


def test_review_waits_for_delivery_and_preserves_rule_and_evidence(tmp_path):
    box = Outbox(tmp_path / 'reviews.db')
    seed(box)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={'observations': ['Person visible'], 'recommendedActions': ['Check access'],
                                        'limitations': ['Cannot infer authorization']})
    with httpx.Client(base_url='http://test', transport=httpx.MockTransport(handler)) as client:
        assert not process_one(box, 'camera', client)
        assert not calls
        box.acknowledge(box[0])
        assert process_one(box, 'camera', client)
    payload = box[0]
    assert payload['type'] == 'restricted_entry' and payload['severity'] == 'medium'
    assert payload['confidence'] == .8 and payload['status'] == 'active'
    assert payload['modelProvider'] == 'rule-engine'
    assert payload['evidence']['clipUrl'] == '/recorded'
    assert payload['detailedNarrative'] == ['Person visible']
    box.close()


def test_failures_consume_durable_budget_and_do_not_erase_incident(tmp_path):
    path = tmp_path / 'reviews.db'
    box = Outbox(path)
    seed(box)
    box.acknowledge(box[0])
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429)
    with httpx.Client(base_url='http://test', transport=httpx.MockTransport(handler)) as client:
        assert process_one(box, 'camera', client, daily_limit=1)
        assert 'HTTPStatusError' in box[0]['reviewNotes'][-1]
        box.acknowledge(box[0])
        box.close()
        box = Outbox(path)
        seed(box, 'two')
        box.acknowledge(box[0])
        assert process_one(box, 'camera', client, daily_limit=1)
        assert 'daily request cap' in box[0]['reviewNotes'][-1]
        assert len(calls) == 1
    box.close()


def test_budget_is_shared_across_source_journals(tmp_path):
    budget = tmp_path / 'shared-budget.db'
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(503)
    with httpx.Client(base_url='http://test', transport=httpx.MockTransport(handler)) as client:
        for identifier in ('source-a', 'source-b'):
            box = Outbox(tmp_path / (identifier + '.db'))
            seed(box)
            box.acknowledge(box[0])
            assert process_one(box, 'camera', client, daily_limit=1, budget_path=budget)
            box.close()
    assert len(calls) == 1
