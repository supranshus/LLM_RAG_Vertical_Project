import logging
import time

import pytest

from app.core.errors import ForbiddenError, UnauthorizedError
from tests.auth_helpers import OTHER_KEY, make_token, test_validator

V = test_validator()


def test_valid_token():
    claims = V.validate(make_token(roles=["Admin"]))
    assert claims.roles == frozenset({"Admin"})
    assert (claims.oid, claims.tid, claims.name, claims.preferred_username) == (
        "oid-alice",
        "tenant-123",
        "Alice",
        "alice@org",
    )


def test_no_roles_claim_means_no_roles():
    assert V.validate(make_token()).roles == frozenset()


def test_api_uri_audience_accepted():
    assert V.validate(make_token(aud="api://client-456")).oid == "oid-alice"


@pytest.mark.parametrize(
    "overrides",
    [
        {"tid": "other-tenant"},
        {"iss": "https://login.microsoftonline.com/other/v2.0"},
        {"aud": "someone-else"},
        {"exp": int(time.time()) - 3600},
        {"oid": None},
    ],
)
def test_rejected_401(overrides):
    with pytest.raises(UnauthorizedError):
        V.validate(make_token(**overrides))


def test_bad_signature_401():
    with pytest.raises(UnauthorizedError):
        V.validate(make_token(key=OTHER_KEY))


def test_garbage_token_401():
    with pytest.raises(UnauthorizedError):
        V.validate("not-a-jwt")


def test_key_lookup_failure_401():
    def broken_resolver(_token):
        raise RuntimeError("JWKS unreachable")

    validator = type(V)("tenant-123", "client-456", key_resolver=broken_resolver)
    with pytest.raises(UnauthorizedError):
        validator.validate(make_token())


def test_guest_403():
    with pytest.raises(ForbiddenError, match="Guest"):
        V.validate(make_token(acct=1))


def test_missing_acct_403_and_logged(caplog):
    with caplog.at_level(logging.ERROR), pytest.raises(ForbiddenError):
        V.validate(make_token(acct=None))
    assert "acct optional claim" in caplog.text


def test_token_without_api_scope_403():
    with pytest.raises(ForbiddenError, match="access_as_user"):
        V.validate(make_token(scp=None))
    with pytest.raises(ForbiddenError, match="access_as_user"):
        V.validate(make_token(scp="User.Read"))


def test_scope_among_several_is_accepted():
    assert V.validate(make_token(scp="openid access_as_user")).oid == "oid-alice"


def test_app_only_token_403(caplog):
    with caplog.at_level(logging.ERROR), pytest.raises(ForbiddenError, match="signed-in user"):
        V.validate(make_token(idtyp="app", scp=None, acct=None))
    assert "acct optional claim" not in caplog.text


def test_v1_token_logs_issuer_and_version_hint(caplog):
    v1_issuer = "https://sts.windows.net/tenant-123/"
    with caplog.at_level(logging.WARNING), pytest.raises(UnauthorizedError):
        V.validate(make_token(iss=v1_issuer))
    assert v1_issuer in caplog.text
    assert "https://login.microsoftonline.com/tenant-123/v2.0" in caplog.text
    assert "requestedAccessTokenVersion" in caplog.text
