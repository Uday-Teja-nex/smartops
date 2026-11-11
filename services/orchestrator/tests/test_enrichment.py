import httpx
import pytest
from app.enrichment import EnrichmentRequest, describe_failure, enrich

VALID = {'scene': 'Three people stand near a checkout counter.', 'verdict': 'consistent',
         'observations': ['Person visible.'], 'recommendedActions': ['Check access log.'],
         'limitations': ['Authorization cannot be established from this image.']}


class Provider:
    vision_model = 'qwen2.5vl:3b'

    def review_event_evidence_base64(self, prompt, images, schema):
        assert images == ['aA==']
        assert 'Do not confirm intent' in prompt
        assert set(schema['required']) >= {'scene', 'verdict'}
        return self.result


def request(event='restricted_entry'):
    return EnrichmentRequest(incidentId='one', eventType=event, measuredSummary='Rule fired', imageBase64='aA==')


def test_enrichment_returns_scene_verdict_and_model_but_no_adjudication_fields():
    provider = Provider()
    provider.result = {**VALID, 'severity': 'critical', 'category': 'Safety'}
    result = enrich(provider, request()).model_dump()
    assert 'severity' not in result and 'category' not in result
    assert result['verdict'] == 'consistent' and result['scene'].startswith('Three people')
    assert result['model'] == 'qwen2.5vl:3b' and result['latencyMs'] >= 0


@pytest.mark.parametrize('result', [
    {'observations': []},
    {**VALID, 'observations': ['x' * 121]},
    {**VALID, 'verdict': 'confirmed intruder'},
    {**VALID, 'scene': ''},
])
def test_invalid_enrichment_does_not_become_operator_copy(result):
    provider = Provider()
    provider.result = result
    with pytest.raises(Exception) as caught:
        enrich(provider, request('test'))
    assert describe_failure(caught.value) == 'model output failed validation'


def response(status, text=''):
    req = httpx.Request('POST', 'https://openrouter.ai/api/v1/chat/completions')
    return httpx.HTTPStatusError('x', request=req, response=httpx.Response(status, text=text, request=req))


@pytest.mark.parametrize('error, reason', [
    (response(429, '{"error":{"message":"Rate limit exceeded: free-models-per-day"}}'),
     'model provider daily request limit reached'),
    (response(429, 'slow down'), 'model provider rate limit reached'),
    (response(401), 'model provider rejected the API key'),
    (response(502), 'model provider error (HTTP 502)'),
    (httpx.ReadTimeout('t'), 'model did not answer in time'),
    (httpx.ConnectError('c'), 'model server unreachable'),
])
def test_failures_have_specific_reasons_without_urls(error, reason):
    assert describe_failure(error) == reason
    assert '://' not in reason and 'openrouter' not in reason


def test_metrics_count_review_outcomes_by_reason(monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as main
    monkeypatch.setattr(main, 'enrich', lambda provider, payload: (_ for _ in ()).throw(response(429, 'free-models-per-day')))
    client = TestClient(main.app)
    body = {'incidentId': 'm', 'eventType': 'crowding', 'measuredSummary': 's', 'imageBase64': 'aA=='}
    assert client.post('/v1/incidents/enrich', json=body).status_code == 503
    text = client.get('/metrics').text
    assert 'smartops_ai_reviews_total{outcome="unavailable",reason="daily_request_limit"}' in text
