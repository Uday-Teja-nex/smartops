import asyncio
import pytest
from app.request_limits import RequestSizeLimit


def run_request(chunks, headers=(), limit=8):
    sent, accepted = [], []
    messages = iter([{'type': 'http.request', 'body': chunk, 'more_body': i < len(chunks) - 1}
                     for i, chunk in enumerate(chunks)])
    async def receive():
        return next(messages, {'type': 'http.disconnect'})
    async def send(message):
        sent.append(message)
    async def downstream(scope, receive, send):
        accepted.append((await receive())['body'])
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
    asyncio.run(RequestSizeLimit(downstream, limit)({'type': 'http', 'headers': headers}, receive, send))
    return sent, accepted


@pytest.mark.parametrize('headers', [[], [(b'content-length', b'1')]])
def test_actual_chunked_size_is_enforced_even_with_false_length(headers):
    sent, accepted = run_request([b'12345', b'6789'], headers)
    assert sent[0]['status'] == 413
    assert accepted == []


def test_exact_limit_replays_body_without_loss():
    sent, accepted = run_request([b'1234', b'5678'])
    assert sent[0]['status'] == 200
    assert accepted == [b'12345678']


def test_large_declared_body_is_rejected_before_receiving():
    sent, accepted = run_request([], [(b'content-length', b'999')])
    assert sent[0]['status'] == 413
    assert accepted == []


@pytest.mark.parametrize('value', [b'-1', b'garbage'])
def test_invalid_length_is_rejected(value):
    sent, accepted = run_request([], [(b'content-length', value)])
    assert sent[0]['status'] == 400
    assert accepted == []


def test_api_installs_body_limit(client):
    response = client.post('/v1/auth/login', content=b'x', headers={'Content-Length': str(3 * 1024 * 1024)})
    assert response.status_code == 413


def test_streaming_response_and_disconnect_are_preserved():
    sent = []
    incoming = iter([{'type': 'http.request', 'body': b'', 'more_body': False},
                     {'type': 'http.disconnect'}])
    async def receive():
        return next(incoming)
    async def send(message):
        sent.append(message)
    async def stream(scope, receive, send):
        assert (await receive())['type'] == 'http.request'
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'data: first\n\n', 'more_body': True})
        assert (await receive())['type'] == 'http.disconnect'
        await send({'type': 'http.response.body', 'body': b'', 'more_body': False})
    asyncio.run(RequestSizeLimit(stream, 8)({'type': 'http', 'headers': []}, receive, send))
    assert sent[1]['body'] == b'data: first\n\n'
    assert sent[1]['more_body'] is True
