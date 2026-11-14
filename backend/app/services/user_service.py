from app.core.security import CurrentUser, TokenClaims
from app.repositories.user_repo import UserRepository


class UserService:
    def __init__(self, users: UserRepository):
        self.users = users

    def sync_user(self, claims: TokenClaims) -> CurrentUser:
        """Record the signed-in user (created on first sign-in) and return who they are."""
        user = self.users.upsert_from_identity(
            claims.oid, claims.preferred_username, claims.name or claims.preferred_username
        )
        return CurrentUser(
            id=user.id,
            entra_oid=user.entra_oid,
            email=user.email,
            display_name=user.display_name,
            roles=claims.roles,
        )
