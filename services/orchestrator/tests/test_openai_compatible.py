import json

import httpx
import pytest

from app.providers.openai_compatible import OpenAICompatibleProvider


def make_provider(handler):
    return OpenAICompatibleProvider('https://example.test/v1', 'test-key', 'text', 'vision',
                                    transport=httpx.MockTransport(handler))


def test_vision_contract_uses_images_and_validates_response():
    def handler(request):
        assert request.url.path == '/v1/chat/completions'
        assert request.headers['Authorization'] == 'Bearer test-key'
        body = json.loads(request.content)
        assert body['model'] == 'vision'
        assert body['messages'][0]['content'][1]['image_url']['url'] == 'data:image/jpeg;base64,aGVsbG8='
        assert body['response_format']['json_schema']['schema']['type'] == 'object'
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{"verdict":"doubt"}'}}]})
    assert make_provider(handler).review_event_evidence_base64('Check', ['aGVsbG8='], {'type':'object'}) == {'verdict':'doubt'}


@pytest.mark.parametrize('choice', [
    {'finish_reason':'length','message':{'content':'{}'}},
    {'finish_reason':'stop','message':{'refusal':'No','content':'{}'}},
    {'finish_reason':'stop','message':{'content':'[]'}},
    {'finish_reason':'stop','message':{'content':'not JSON'}},
])
def test_incomplete_or_invalid_responses_never_become_reviews(choice):
    provider=make_provider(lambda _:httpx.Response(200,json={'choices':[choice]}))
    with pytest.raises(ValueError):
        provider.summarize_incident('Summarize')


def test_rate_limit_propagates_without_paid_fallback():
    provider=make_provider(lambda _:httpx.Response(429,json={'error':'quota'}))
    with pytest.raises(httpx.HTTPStatusError):
        provider.summarize_incident('Summarize')


def test_openrouter_free_only_rejects_paid_model():
    with pytest.raises(ValueError,match='free'):
        OpenAICompatibleProvider('https://openrouter.ai/api/v1','key','paid/model','paid/model',free_only=True)


def test_openrouter_sends_privacy_and_parameter_constraints():
    def handler(request):
        body = json.loads(request.content)
        assert body['provider'] == {'data_collection': 'deny', 'require_parameters': True}
        assert body['reasoning'] == {'effort': 'none'}
        assert body['max_tokens'] == 1024
        assert 'models' not in body
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]})
    provider = OpenAICompatibleProvider('https://openrouter.ai/api/v1', 'key', 'model:free',
                                       'model:free', free_only=True, transport=httpx.MockTransport(handler))
    assert provider.summarize_incident('test') == {}


def test_remote_credentials_require_https():
    with pytest.raises(ValueError, match='HTTPS'):
        OpenAICompatibleProvider('http://openrouter.ai/api/v1', 'key', 'model:free', 'model:free')


def test_factory_free_only_defaults_on(monkeypatch):
    from app.providers.factory import get_model_provider

    monkeypatch.setenv('SMARTOPS_MODEL_PROVIDER', 'openrouter')
    monkeypatch.setenv('SMARTOPS_MODEL_API_KEY', 'test-key')
    monkeypatch.setenv('SMARTOPS_TEXT_MODEL', 'paid/model')
    monkeypatch.setenv('SMARTOPS_VISION_MODEL', 'model:free')
    monkeypatch.delenv('SMARTOPS_OPENROUTER_FREE_ONLY', raising=False)
    monkeypatch.delenv('SMARTOPS_MODEL_BASE_URL', raising=False)
    with pytest.raises(ValueError, match='free'):
        get_model_provider()
