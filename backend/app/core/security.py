import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import jwt

from app.core.errors import ForbiddenError, UnauthorizedError

logger = logging.getLogger(__name__)

ADMIN_ROLE = "Admin"
MEMBER_ACCOUNT = 0
GUEST_ACCOUNT = 1


@dataclass(frozen=True)
class TokenClaims:
    oid: str
    tid: str
    name: str
    preferred_username: str
    roles: frozenset[str]


@dataclass(frozen=True)
class CurrentUser:
    id: int
    entra_oid: str
    email: str
    display_name: str
    roles: frozenset[str]

    @property
    def is_admin(self) -> bool:
        return ADMIN_ROLE in self.roles


class TokenValidator:
    """Validates Entra ID v2 access tokens issued for this API by our own tenant."""

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        key_resolver: Callable[[str], Any] | None = None,
        required_scope: str = "access_as_user",
    ):
        self.tenant_id = tenant_id
        self.required_scope = required_scope
        self.audiences = [client_id, f"api://{client_id}"]
        self.issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"
        if key_resolver is None:
            jwks = jwt.PyJWKClient(
                f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
                cache_keys=True,
            )

            def key_resolver(token: str) -> Any:
                return jwks.get_signing_key_from_jwt(token).key

        self._key_resolver = key_resolver

    def validate(self, token: str) -> TokenClaims:
        try:
            key = self._key_resolver(token)
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.audiences,
                issuer=self.issuer,
                leeway=60,
                options={"require": ["exp", "iat", "oid", "tid"]},
            )
        except jwt.InvalidIssuerError as exc:
            # The issuer is not secret, and naming it makes a common setup mistake obvious.
            actual = jwt.decode(token, options={"verify_signature": False}).get("iss")
            logger.warning(
                "Rejected access token: issuer %s, expected %s. If the issuer is "
                "https://sts.windows.net/..., the app registration issues v1 tokens: set "
                "requestedAccessTokenVersion to 2 in its manifest",
                actual,
                self.issuer,
            )
            raise UnauthorizedError("Invalid or expired token") from exc
        except Exception as exc:
            logger.info("Rejected access token: %s", type(exc).__name__)
            raise UnauthorizedError("Invalid or expired token") from exc

        if claims["tid"] != self.tenant_id:
            raise UnauthorizedError("Invalid or expired token")

        # Other apps in the tenant can get app-only tokens for this API; only accept
        # tokens issued to a signed-in user through our delegated scope.
        if claims.get("idtyp") == "app":
            raise ForbiddenError("Only tokens issued to a signed-in user are accepted")
        if self.required_scope not in str(claims.get("scp", "")).split():
            raise ForbiddenError(f"Token is missing the {self.required_scope} scope")

        if "acct" not in claims:
            logger.error(
                "Token has no 'acct' claim; add the acct optional claim to the access token "
                "in the app registration"
            )
            raise ForbiddenError("Account type could not be verified")
        if claims["acct"] != MEMBER_ACCOUNT:
            raise ForbiddenError("Guest accounts are not allowed")

        return TokenClaims(
            oid=claims["oid"],
            tid=claims["tid"],
            name=claims.get("name", ""),
            preferred_username=claims.get("preferred_username", ""),
            roles=frozenset(claims.get("roles", [])),
        )
