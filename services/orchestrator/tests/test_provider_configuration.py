import pytest

from app.providers.factory import get_model_provider


def test_default_requests_bound_model_resources(monkeypatch):
    monkeypatch.delenv('SMARTOPS_MODEL_TIMEOUT_SECONDS', raising=False)
    provider = get_model_provider()
    assert provider.timeout_seconds == 30
    payloads = []
    monkeypatch.setattr(provider, 'is_loaded', lambda model: True)
    monkeypatch.setattr(provider, '_post_chat', lambda payload: payloads.append(payload) or {'message': {'content': '{}'}})
    provider.review_event_evidence_base64('Review visible evidence', ['image'])
    provider.summarize_incident('Summarize')
    for payload in payloads:
        assert payload['options']['num_batch'] == 32
        assert payload['options']['num_ctx'] == 2048
        assert payload['options']['num_predict'] == 256
        assert payload['keep_alive'] == '60m'


@pytest.mark.parametrize('value', ['nan', 'inf', '-1', '0', 'oops'])
def test_invalid_timeout_fails_configuration(monkeypatch, value):
    monkeypatch.setenv('SMARTOPS_MODEL_TIMEOUT_SECONDS', value)
    with pytest.raises(ValueError, match='SMARTOPS_MODEL_TIMEOUT_SECONDS'):
        get_model_provider()


def _status_error(status):
    import httpx
    request = httpx.Request('POST', 'https://provider.test/v1/chat/completions')
    return httpx.HTTPStatusError('x', request=request, response=httpx.Response(status, request=request))


class FakeProvider:
    def __init__(self, model, outcome):
        self.vision_model, self.outcome, self.calls = model, outcome, 0

    def review_event_evidence_base64(self, prompt, images, schema=None):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.mark.parametrize('failure', [_status_error(429), _status_error(503), __import__('httpx').ReadTimeout('t')])
def test_fallback_answers_when_primary_is_unavailable_and_names_the_model(failure):
    from app.enrichment import EnrichmentRequest, enrich
    from app.providers.fallback import FallbackProvider
    valid = {'scene': 's', 'verdict': 'unclear', 'observations': [], 'recommendedActions': [], 'limitations': []}
    primary, local = FakeProvider('nemotron:free', failure), FakeProvider('qwen2.5vl:3b', valid)
    result = enrich(FallbackProvider(primary, local), EnrichmentRequest(
        incidentId='i', eventType='crowding', measuredSummary='m', imageBase64='aA=='))
    assert result.model == 'qwen2.5vl:3b (fallback)' and local.calls == 1


def test_fallback_is_not_used_for_bad_output_or_auth_errors():
    from app.providers.fallback import FallbackProvider
    for failure in (ValueError('bad json'), _status_error(401)):
        primary, local = FakeProvider('p', failure), FakeProvider('l', {})
        with pytest.raises(type(failure)):
            FallbackProvider(primary, local).review_event_evidence_base64('p', ['aA=='])
        assert local.calls == 0


def test_only_local_ollama_may_be_a_fallback(monkeypatch):
    monkeypatch.setenv('SMARTOPS_MODEL_FALLBACK', 'openrouter')
    with pytest.raises(ValueError, match='only'):
        get_model_provider()
    monkeypatch.setenv('SMARTOPS_MODEL_FALLBACK', 'ollama')
    monkeypatch.setenv('SMARTOPS_MODEL_PROVIDER', 'openrouter')
    monkeypatch.setenv('SMARTOPS_MODEL_API_KEY', 'k')
    monkeypatch.setenv('SMARTOPS_TEXT_MODEL', 'a:free')
    monkeypatch.setenv('SMARTOPS_VISION_MODEL', 'b:free')
    from app.providers.fallback import FallbackProvider
    provider = get_model_provider()
    assert isinstance(provider, FallbackProvider) and provider.fallback.vision_model == 'qwen2.5vl:3b'


def test_ollama_availability_reports_missing_model_and_warm_state(monkeypatch):
    import httpx
    from app.providers.ollama import OllamaModelProvider

    real_client = httpx.Client

    def client_for(tags, loaded):
        def handler(request):
            return httpx.Response(200, json={'models': [{'name': n} for n in (tags if request.url.path == '/api/tags' else loaded)]})
        return lambda **kwargs: real_client(transport=httpx.MockTransport(handler), base_url='http://o')

    provider = OllamaModelProvider('http://o', 'llama3.2:3b', 'qwen2.5vl:3b')
    monkeypatch.setattr(httpx, 'Client', client_for(['llama3.2:3b'], []))
    assert provider.availability() == {'ok': False, 'model': 'qwen2.5vl:3b',
                                       'detail': 'model qwen2.5vl:3b is not installed in Ollama'}
    monkeypatch.setattr(httpx, 'Client', client_for(['qwen2.5vl:3b'], ['qwen2.5vl:3b']))
    assert provider.availability()['detail'] == 'loaded and warm'



def test_unloaded_model_fails_fast_and_loads_once_in_the_background(monkeypatch):
    import threading
    from app.enrichment import describe_failure
    from app.providers.base import ModelLoading
    from app.providers.ollama import OllamaModelProvider
    provider = OllamaModelProvider('http://o', 'llama3.2:3b', 'qwen2.5vl:3b')
    started, release = [], threading.Event()
    monkeypatch.setattr(provider, 'is_loaded', lambda model: False)
    monkeypatch.setattr(provider, '_post_chat', lambda payload: pytest.fail('must not wait on an unloaded model'))

    real_thread = threading.Thread

    class RecordingThread(real_thread):
        def __init__(self, target, **kwargs):
            def run():
                started.append(kwargs.get('name'))
                release.wait(2)
                provider._loading.release()
            super().__init__(target=run, **kwargs)

    monkeypatch.setattr(threading, 'Thread', RecordingThread)
    for _ in range(3):
        with pytest.raises(ModelLoading) as caught:
            provider.review_event_evidence_base64('p', ['aA=='])
    release.set()
    assert started == ['ollama-load-qwen2.5vl:3b']
    assert describe_failure(caught.value) == 'qwen2.5vl:3b is loading (about 2 minutes); later incidents will be reviewed'


def test_background_load_uses_the_same_runner_options_as_reviews(monkeypatch):
    import httpx
    from app.providers import ollama
    sent = []
    real_client = httpx.Client

    def handler(request):
        import json
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={})

    monkeypatch.setattr(httpx, 'Client', lambda **kw: real_client(transport=httpx.MockTransport(handler)))
    provider = ollama.OllamaModelProvider('http://o', 'llama3.2:3b', 'qwen2.5vl:3b')
    provider.start_background_load('qwen2.5vl:3b')
    import time
    for _ in range(50):
        if sent:
            break
        time.sleep(0.02)
    assert sent[0]['options'] == ollama.LOAD_OPTIONS == {'num_ctx': 2048, 'num_batch': 32, 'num_thread': 4}
