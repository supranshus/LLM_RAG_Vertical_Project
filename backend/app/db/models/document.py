from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._common import utcnow


class Document(Base):
    __tablename__ = "documents"
    # Vector ids are built from document ids, so an id must never be handed out twice.
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(16), index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(200))
    size_bytes: Mapped[int]
    storage_path: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="processing")
    error_message: Mapped[str | None] = mapped_column(Text)
    chunk_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
