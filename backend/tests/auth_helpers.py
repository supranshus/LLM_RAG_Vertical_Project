"""Locally signed Entra-style tokens, so auth tests run without Microsoft."""

import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.security import TokenValidator

TENANT_ID = "tenant-123"
CLIENT_ID = "client-456"
TEST_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_token(key=TEST_KEY, **overrides: Any) -> str:
    """A signed v2 access token; an override of None removes that claim."""
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
        "aud": CLIENT_ID,
        "tid": TENANT_ID,
        "oid": "oid-alice",
        "name": "Alice",
        "preferred_username": "alice@org",
        "acct": 0,
        "scp": "access_as_user",
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})


def test_validator() -> TokenValidator:
    return TokenValidator(TENANT_ID, CLIENT_ID, key_resolver=lambda _token: TEST_KEY.public_key())


test_validator.__test__ = False  # not a pytest test
