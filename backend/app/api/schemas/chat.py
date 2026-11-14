from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.types import KnowledgeScope

MAX_MESSAGE_CHARS = 8000


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    knowledge_scope: KnowledgeScope = "none"


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    knowledge_scope: KnowledgeScope
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    content: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS)
    ]


class SourceRead(BaseModel):
    document_id: int
    filename: str
    page: int | None


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    model: str | None
    sources: list[SourceRead] | None
    created_at: datetime
