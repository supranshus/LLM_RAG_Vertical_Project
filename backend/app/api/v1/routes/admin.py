from fastapi import APIRouter, Depends

from app.api.deps import get_admin_service, require_admin
from app.api.schemas.admin import AdminUserRead
from app.core.security import CurrentUser
from app.services.admin_service import AdminService

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserRead])
def list_users(
    _admin: CurrentUser = Depends(require_admin),
    admin: AdminService = Depends(get_admin_service),
) -> list[AdminUserRead]:
    return [
        AdminUserRead(
            id=s.user.id,
            email=s.user.email,
            display_name=s.user.display_name,
            created_at=s.user.created_at,
            last_seen_at=s.user.last_seen_at,
            conversation_count=s.conversation_count,
            message_count=s.message_count,
        )
        for s in admin.list_users()
    ]
