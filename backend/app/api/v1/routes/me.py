from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.schemas.user import MeRead
from app.core.security import CurrentUser

router = APIRouter(prefix="/api/v1", tags=["me"])


@router.get("/me", response_model=MeRead)
def read_me(user: CurrentUser = Depends(get_current_user)) -> MeRead:
    return MeRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=sorted(user.roles),
        is_admin=user.is_admin,
    )
