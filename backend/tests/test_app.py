import pytest
from fastapi.testclient import TestClient

from app.core.errors import NotFoundError


@pytest.fixture
def client_with_route(app):
    @app.get("/boom")
    def boom():
        raise NotFoundError("nope")

    @app.get("/crash")
    def crash():
        raise RuntimeError("secret")

    return TestClient(app, raise_server_exceptions=False)


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok", "vector_store": "ok"}


def test_swagger_ui_can_sign_in_with_entra(client):
    schemes = client.get("/openapi.json").json()["components"]["securitySchemes"]
    flow = schemes["OAuth2AuthorizationCodeBearer"]["flows"]["authorizationCode"]
    entra = "https://login.microsoftonline.com/tenant-123/oauth2/v2.0"
    assert flow["authorizationUrl"] == f"{entra}/authorize"
    assert flow["tokenUrl"] == f"{entra}/token"
    assert all(scope.startswith("api://client-456/") for scope in flow["scopes"])

    docs = client.get("/swagger").text
    assert "client-456" in docs
    assert "usePkceWithAuthorizationCodeGrant" in docs


def test_root_opens_swagger(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/swagger"


def test_request_id_echoed_and_generated(client):
    assert client.get("/health", headers={"X-Request-ID": "abc"}).headers["X-Request-ID"] == "abc"
    assert len(client.get("/health").headers["X-Request-ID"]) == 12


def test_app_error_shape(client_with_route):
    r = client_with_route.get("/boom", headers={"X-Request-ID": "r1"})
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "not_found", "message": "nope", "request_id": "r1"}}


def test_unhandled_error_is_500_json(client_with_route):
    r = client_with_route.get("/crash", headers={"X-Request-ID": "r2"})
    assert r.status_code == 500
    assert r.json() == {
        "error": {"code": "internal_error", "message": "Internal server error", "request_id": "r2"}
    }
    assert "secret" not in r.text


def test_validation_error_shape(client_with_route, app):
    @app.get("/needs-int")
    def needs_int(n: int):
        return {"n": n}

    r = client_with_route.get("/needs-int", params={"n": "abc"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert "n" in r.json()["error"]["message"]


def test_health_503_when_database_down(app, client):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.api.deps import get_session_factory

    def refuse():
        raise OSError("database is down")

    broken = create_engine("sqlite://", creator=refuse)
    app.dependency_overrides[get_session_factory] = lambda: sessionmaker(bind=broken)
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json() == {"status": "degraded", "database": "error", "vector_store": "ok"}
