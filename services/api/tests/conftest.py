import os
import sys
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

# Configure before app imports: SQLite file DB (shared across TestClient
# threads), demo seed on, deterministic secrets. The DB filename includes the
# PID so concurrent test runs never fight over one file.
_DB_PATH = Path(f"./test-smartops-{os.getpid()}.db").resolve()
os.environ["SMARTOPS_DATABASE_URL"] = f"sqlite:///{_DB_PATH.as_posix()}"
os.environ.setdefault("SMARTOPS_JWT_SECRET", "test-secret")
os.environ.setdefault("SMARTOPS_INTERNAL_TOKEN", "test-internal-token")
os.environ.setdefault("SMARTOPS_EVIDENCE_STORAGE_ENABLED", "false")


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from unittest.mock import Mock, patch

    from app.db import Base, engine
    from app.main import app

    Base.metadata.drop_all(bind=engine)
    limiter = Mock()
    limiter.eval.return_value = 0
    # Session-scoped login fixtures run before function-scoped transport mocks.
    with patch('app.login_limits.client', return_value=limiter), TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if _DB_PATH.exists():
        _DB_PATH.unlink()


@pytest.fixture(autouse=True)
def isolate_event_transport(monkeypatch):
    # Unit/API tests exercise persistence without waiting for a live Redis host.
    from unittest.mock import Mock
    from app import events
    monkeypatch.setattr(events, '_redis', Mock())
    from app import login_limits
    limiter = Mock()
    limiter.eval.return_value = 0
    monkeypatch.setattr(login_limits, 'client', lambda: limiter)


def login(client, email: str, password: str = "smartops-demo") -> dict[str, str]:
    response = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture(scope="session")
def admin_headers(client):
    return login(client, "admin@smartops.local")


@pytest.fixture(scope="session")
def supervisor_headers(client):
    return login(client, "supervisor@smartops.local")


@pytest.fixture(scope="session")
def operator_headers(client):
    return login(client, "operator@smartops.local")


@pytest.fixture(scope="session")
def viewer_headers(client):
    return login(client, "viewer@smartops.local")


@pytest.fixture(scope="session")
def service_headers():
    return {"X-Internal-Token": "test-internal-token"}
