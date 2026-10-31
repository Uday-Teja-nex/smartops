from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.auth import Principal, get_current_principal
from app.db import engine
from app.main import app
from app.models import OrganizationModel, BuildingModel


def test_org_and_topology_follow_authenticated_workspace(client, admin_headers):
    existing_sources = client.get('/v1/sources', headers=admin_headers).json()
    assert existing_sources
    with Session(engine) as session:
        session.add(OrganizationModel(id='org-boundary', name='Other workspace', slug='boundary-test',
                                      settings={}, created_at=datetime.now(UTC)))
        session.add(BuildingModel(id='building-boundary', org_id='org-boundary', name='Private building',
                                 address='Test', timezone='UTC'))
        session.commit()
    principal = Principal('boundary-user', 'Test', 'test@example.test', 'admin', 'org-boundary', 'user')
    app.dependency_overrides[get_current_principal] = lambda: principal
    try:
        assert client.get('/v1/org').json()['id'] == 'org-boundary'
        assert client.get('/v1/users').json() == []
        report = client.get('/v1/reports/summary', params={
            'start': '2026-07-01T00:00:00Z', 'end': '2026-07-31T00:00:00Z'}).json()
        assert report['totalIncidents'] == 0
        assert report['averageAckMinutes'] is None
        bootstrap = client.get('/v1/bootstrap').json()
        assert bootstrap['sources'] == [] and bootstrap['incidents'] == []
        for route in ('sources', 'incidents', 'evidence'):
            assert client.get('/v1/' + route).json() == []
        assert client.get('/v1/sources/' + existing_sources[0]['id']).status_code == 404
        from app.routers.pipeline import _snapshot_payload
        import json
        snapshot = json.loads(_snapshot_payload('org-boundary'))
        assert snapshot == {'incidents': [], 'sources': []}
        assert [b['id'] for b in client.get('/v1/buildings').json()] == ['building-boundary']
        assert client.put('/v1/org/settings', json={'settings': {'boundaryMarker': True}}).status_code == 200
        with Session(engine) as session:
            assert session.get(OrganizationModel, 'org-boundary').settings['boundaryMarker']
            assert 'boundaryMarker' not in session.get(OrganizationModel, 'org-demo').settings
        principal.org_id = 'missing-workspace'
        assert client.get('/v1/org').status_code == 404
        assert client.get('/v1/buildings').json() == []
    finally:
        app.dependency_overrides.pop(get_current_principal, None)
        with Session(engine) as session:
            session.delete(session.get(BuildingModel, 'building-boundary'))
            session.delete(session.get(OrganizationModel, 'org-boundary'))
            session.commit()
