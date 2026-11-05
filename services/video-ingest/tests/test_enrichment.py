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


def test_quarantined_incident_does_not_spend_review_budget(tmp_path):
    from unittest.mock import Mock
    box = Outbox(tmp_path / 'quarantined-review.db')
    seed(box)
    box.quarantine(box[0], 422)
    client = Mock()
    assert not process_one(box, 'camera', client)
    client.post.assert_not_called()
    assert box.db.execute('SELECT count(*) FROM review_budget').fetchone()[0] == 0
    box.close()


def test_review_waits_for_delivery_and_preserves_rule_and_evidence(tmp_path):
    box = Outbox(tmp_path / 'reviews.db')
    seed(box)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={'scene': 'One person at a doorway.', 'verdict': 'consistent',
                                        'observations': ['Person visible'], 'recommendedActions': ['Check access'],
                                        'limitations': ['Cannot infer authorization'],
                                        'model': 'qwen2.5vl:3b', 'latencyMs': 2100})
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
    assert payload['detailedNarrative'] == ['One person at a doorway.', 'Person visible']
    assert ('AI review by qwen2.5vl:3b (2.1 s): image looks consistent with the measured event. '
            'Rule decision unchanged.') in payload['reviewNotes']
    assert payload['detectionSummary']['aiReview'] == {'model': 'qwen2.5vl:3b', 'verdict': 'consistent',
                                                        'latencyMs': 2100}
    box.close()


def test_unavailable_review_states_the_orchestrators_reason(tmp_path):
    box = Outbox(tmp_path / 'reason.db')
    seed(box)
    box.acknowledge(box[0])
    handler = lambda request: httpx.Response(503, json={'detail': 'model provider daily request limit reached'})
    with httpx.Client(base_url='http://test', transport=httpx.MockTransport(handler)) as client:
        assert process_one(box, 'camera', client)
    assert box[0]['reviewNotes'][-1] == 'AI review unavailable: model provider daily request limit reached.'
    assert not box[0].get('detailedNarrative')
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
        assert box[0]['reviewNotes'][-1] == 'AI review unavailable: AI service returned HTTP 429.'
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
