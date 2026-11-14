from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scope: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    error_message: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime
