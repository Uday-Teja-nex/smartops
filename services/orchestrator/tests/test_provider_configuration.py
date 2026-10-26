import pytest

from app.providers.factory import get_model_provider


def test_default_requests_bound_model_resources(monkeypatch):
    monkeypatch.delenv('SMARTOPS_MODEL_TIMEOUT_SECONDS', raising=False)
    provider = get_model_provider()
    assert provider.timeout_seconds == 30
    payloads = []
    monkeypatch.setattr(provider, '_post_chat', lambda payload: payloads.append(payload) or {'message': {'content': '{}'}})
    provider.review_event_evidence_base64('Review visible evidence', ['image'])
    provider.summarize_incident('Summarize')
    for payload in payloads:
        assert payload['options']['num_batch'] == 32
        assert payload['options']['num_ctx'] == 2048
        assert payload['options']['num_predict'] == 256
        assert payload['keep_alive'] == '10m'


@pytest.mark.parametrize('value', ['nan', 'inf', '-1', '0', 'oops'])
def test_invalid_timeout_fails_configuration(monkeypatch, value):
    monkeypatch.setenv('SMARTOPS_MODEL_TIMEOUT_SECONDS', value)
    with pytest.raises(ValueError, match='SMARTOPS_MODEL_TIMEOUT_SECONDS'):
        get_model_provider()
