from sqlalchemy import select
from app.db import SessionLocal
from app.models import EvidenceAccessModel


def test_restricted_evidence_roles_and_issuance_audit(
    client, service_headers, viewer_headers, operator_headers, monkeypatch,
):
    from app.routers import evidence
    from app import storage
    monkeypatch.setattr(evidence.settings, 'evidence_storage_enabled', True)
    issued = []
    def presign(key):
        issued.append(key)
        return 'https://storage.example.com/signed'
    monkeypatch.setattr(storage, 'presign_get_url', presign)
    source = client.post('/v1/sources', headers=service_headers, json={
        'name': 'Audit camera', 'buildingId': 'bldg-north-01', 'floor': 'L1',
        'zone': 'Lobby Atrium', 'sourceType': 'file', 'sourceUri': '/app/sample-data/input/audit.mp4',
    }).json()
    item = client.post('/v1/evidence', headers=service_headers, json={
        'sourceId': source['id'], 'kind': 'snapshot', 'objectKey': 'tests/audit.jpg',
        'contentType': 'image/jpeg', 'restricted': True,
    }).json()
    path = '/v1/evidence/' + item['id'] + '/url'
    assert client.get(path, headers=viewer_headers).status_code == 403
    assert client.get(path, headers=service_headers).status_code == 403
    assert issued == []
    response = client.get(path, headers=operator_headers)
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    with SessionLocal() as session:
        rows = session.scalars(select(EvidenceAccessModel).where(EvidenceAccessModel.evidence_id == item['id'])).all()
        assert len(rows) == 1
        assert rows[0].actor_id == 'usr-operator'
        assert rows[0].org_id == 'org-demo'
    assert issued == ['tests/audit.jpg']


def test_evidence_audit_migration_round_trip():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect
    path = Path(__file__).resolve().parents[1] / 'alembic/versions/0002_evidence_access.py'
    spec = importlib.util.spec_from_file_location('evidence_access_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    try:
        with engine.begin() as connection:
            migration.op = Operations(MigrationContext.configure(connection))
            migration.upgrade()
            schema = inspect(connection)
            assert {column['name'] for column in schema.get_columns('evidence_access')} == {
                'id', 'org_id', 'evidence_id', 'actor_id', 'actor_role', 'created_at',
            }
            assert len(schema.get_foreign_keys('evidence_access')) == 2
            assert len(schema.get_indexes('evidence_access')) == 2
            migration.downgrade()
            assert not inspect(connection).has_table('evidence_access')
    finally:
        engine.dispose()
