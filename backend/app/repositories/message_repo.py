from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Message


class MessageRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(
        self,
        conversation_id: int,
        role: str,
        content: str,
        *,
        model: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        sources: list[dict[str, Any]] | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            sources=sources,
        )
        self.session.add(message)
        self.session.commit()
        self.session.refresh(message)
        return message

    def list_for_conversation(
        self, conversation_id: int, limit: int | None = None
    ) -> list[Message]:
        """Messages oldest first; with a limit, only the most recent `limit` messages."""
        query = select(Message).where(Message.conversation_id == conversation_id)
        if limit is None:
            return list(self.session.scalars(query.order_by(Message.id)))
        latest = list(self.session.scalars(query.order_by(Message.id.desc()).limit(limit)))
        return list(reversed(latest))
