from starlette.routing import Match


def test_stream_url_reaches_stream_handler():
    from app.main import app

    scope = {"type": "http", "path": "/v1/incidents/stream", "method": "GET"}
    matched = next(route for route in app.routes if route.matches(scope)[0] == Match.FULL)
    assert matched.endpoint.__name__ == "stream_events"


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
