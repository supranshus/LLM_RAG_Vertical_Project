from pydantic import BaseModel


class MeRead(BaseModel):
    id: int
    email: str
    display_name: str
    roles: list[str]
    is_admin: bool
