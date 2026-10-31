import json
from unittest.mock import Mock


def test_pipeline_hides_other_workspaces_and_global_totals(client, viewer_headers, monkeypatch):
    from app.routers import pipeline
    own = client.get('/v1/sources', headers=viewer_headers).json()[0]['id']
    transport = Mock()
    transport.scan_iter.return_value = ['own', 'foreign', 'malformed']
    transport.get.side_effect = [json.dumps({'sourceId': own, 'state': 'completed'}),
                                 json.dumps({'sourceId': 'foreign', 'state': 'failed'}), 'not-json']
    monkeypatch.setattr(pipeline, 'redis_client', transport)
    response = client.get('/v1/pipeline/status', headers=viewer_headers)
    assert response.status_code == 200
    body = response.json()
    assert [row['sourceId'] for row in body['recentStatuses']] == [own]
    assert body['queued'] is None and body['deadLetter'] is None
    transport.llen.assert_not_called()
