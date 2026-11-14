from datetime import datetime

from pydantic import BaseModel


class AdminUserRead(BaseModel):
    id: int
    email: str
    display_name: str
    created_at: datetime
    last_seen_at: datetime
    conversation_count: int
    message_count: int
