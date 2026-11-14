import logging
import os
from pathlib import Path
from unittest.mock import ANY

from app.repositories.user_repo import UserRepository


def test_me_requires_token(client):
    r = client.get("/api/v1/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_me_rejects_invalid_token(client):
    r = client.get("/api/v1/me", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_me_creates_user_and_returns_profile(client, auth_header, db_session):
    r = client.get("/api/v1/me", headers=auth_header())
    assert r.status_code == 200
    assert r.json() == {
        "id": ANY,
        "email": "alice@org",
        "display_name": "Alice",
        "roles": [],
        "is_admin": False,
    }
    assert UserRepository(db_session).get_by_oid("oid-alice") is not None


def test_me_admin(client, admin_header):
    body = client.get("/api/v1/me", headers=admin_header).json()
    assert body["is_admin"] is True
    assert body["roles"] == ["Admin"]


def test_guest_gets_403(client, auth_header):
    r = client.get("/api/v1/me", headers=auth_header(acct=1))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_request_log_line_includes_user(client, auth_header):
    client.get("/api/v1/me", headers={**auth_header(), "X-Request-ID": "log-check-1"})
    for handler in logging.getLogger().handlers:
        handler.flush()
    log_file = Path(os.environ["LOG_DIR"]) / "backend.log"
    lines = [
        line
        for line in log_file.read_text(encoding="utf-8").splitlines()
        if "req=log-check-1" in line and "GET /api/v1/me -> 200" in line
    ]
    assert lines and "user=alice@org" in lines[-1]
