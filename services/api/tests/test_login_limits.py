from unittest.mock import Mock

from redis.exceptions import ConnectionError
from app import login_limits


def test_throttled_login_skips_password_verification(client, monkeypatch):
    from app.routers import auth
    transport = Mock()
    transport.eval.return_value = 27
    monkeypatch.setattr(login_limits, 'client', lambda: transport)
    verify = Mock(return_value=None)
    monkeypatch.setattr(auth, 'authenticate_user', verify)
    response = client.post('/v1/auth/login', json={'email': 'user@example.com', 'password': 'wrong'})
    assert response.status_code == 429
    assert response.headers['retry-after'] == '27'
    verify.assert_not_called()


def test_limiter_outage_fails_closed(client, monkeypatch):
    transport = Mock()
    transport.eval.side_effect = ConnectionError('private connection details')
    monkeypatch.setattr(login_limits, 'client', lambda: transport)
    response = client.post('/v1/auth/login', json={'email': 'operator@smartops.local', 'password': 'smartops-demo'})
    assert response.status_code == 503
    assert 'private' not in response.text


def test_account_normalization_and_private_keys(monkeypatch):
    transport = Mock()
    transport.eval.return_value = 0
    monkeypatch.setattr(login_limits, 'client', lambda: transport)
    login_limits.enforce_login_limit('127.0.0.1', ' USER@example.com ')
    first = transport.eval.call_args.args
    login_limits.enforce_login_limit('127.0.0.1', 'user@example.com')
    assert first == transport.eval.call_args.args
    assert 'user@example.com' not in str(first)
    assert '127.0.0.1' not in str(first)
