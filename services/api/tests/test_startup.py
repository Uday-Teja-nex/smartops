from starlette.routing import Match


def test_stream_url_reaches_stream_handler():
    from app.main import app

    scope = {"type": "http", "path": "/v1/incidents/stream", "method": "GET"}
    def first_match(routes):
        # FastAPI >= 0.16x wraps included routers; descend into them.
        for route in routes:
            if route.matches(scope)[0] != Match.FULL:
                continue
            inner = getattr(route, "original_router", None)
            return first_match(inner.routes) if inner is not None else route
        return None

    assert first_match(app.routes).endpoint.__name__ == "stream_events"


def test_startup_failure_has_traceback(monkeypatch, caplog):
    import pytest
    from app import main

    monkeypatch.setattr(main.settings, "database_url", "postgresql://unavailable")

    def fail():
        raise RuntimeError("migration failed")

    monkeypatch.setattr(main, "run_migrations", fail)
    with pytest.raises(RuntimeError, match="migration failed"):
        main.startup()
    assert any(record.exc_info and "startup" in record.message.lower() for record in caplog.records)


def test_ready_reports_each_dependency(client, monkeypatch):
    from unittest.mock import Mock
    import redis
    monkeypatch.setattr(redis.Redis, 'from_url', Mock(return_value=Mock(ping=Mock(return_value=True))))
    response = client.get('/ready')
    assert response.status_code == 200 and response.json()['checks'] == {'database': 'ok', 'redis': 'ok'}
    monkeypatch.setattr(redis.Redis, 'from_url', Mock(return_value=Mock(ping=Mock(side_effect=redis.ConnectionError()))))
    response = client.get('/ready')
    assert response.status_code == 503
    assert response.json()['checks']['redis'] == 'unavailable (ConnectionError)'


def test_startup_without_migrations_refuses_an_outdated_schema(monkeypatch):
    import pytest
    from app import main
    monkeypatch.setattr(main.settings, 'database_url', 'postgresql+psycopg://x/y')
    monkeypatch.setattr(main.settings, 'run_migrations_on_startup', False)
    monkeypatch.setattr(main, 'schema_revision_status', lambda: ('0003', '0004'))
    with pytest.raises(RuntimeError, match='python -m app.migrate'):
        main.initialize_storage()
