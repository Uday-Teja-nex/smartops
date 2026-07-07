def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "api"


def test_protected_endpoints_require_auth(client):
    assert client.get("/v1/bootstrap").status_code == 401
    assert client.get("/v1/sources").status_code == 401
    assert client.get("/v1/incidents").status_code == 401
    assert client.get("/v1/pipeline/status").status_code == 401


def test_login_rejects_bad_password(client):
    response = client.post(
        "/v1/auth/login",
        json={"email": "admin@smartops.local", "password": "wrong"},
    )
    assert response.status_code == 401


def test_login_returns_token_and_user(client):
    response = client.post(
        "/v1/auth/login",
        json={"email": "operator@smartops.local", "password": "smartops-demo"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["user"]["role"] == "operator"


def test_me_reflects_principal(client, viewer_headers, service_headers):
    me = client.get("/v1/auth/me", headers=viewer_headers)
    assert me.status_code == 200
    assert me.json()["role"] == "viewer"

    service_me = client.get("/v1/auth/me", headers=service_headers)
    assert service_me.status_code == 200
    assert service_me.json()["role"] == "service"


def test_invalid_internal_token_rejected(client):
    response = client.get("/v1/sources", headers={"X-Internal-Token": "nope"})
    assert response.status_code == 401


def test_sse_token_query_param_authenticates(client, viewer_headers):
    # SSE/video clients cannot set headers, so auth accepts ?token=.
    # Use a Redis-free endpoint: unit tests run without a Redis server.
    token = viewer_headers["Authorization"].removeprefix("Bearer ")
    response = client.get(f"/v1/bootstrap?token={token}")
    assert response.status_code == 200
    assert client.get("/v1/bootstrap?token=not-a-jwt").status_code == 401


def test_users_list_is_admin_only(client, admin_headers, operator_headers):
    assert client.get("/v1/users", headers=operator_headers).status_code == 403
    response = client.get("/v1/users", headers=admin_headers)
    assert response.status_code == 200
    roles = {user["role"] for user in response.json()}
    assert {"admin", "supervisor", "operator", "viewer", "security", "ehs"} <= roles
