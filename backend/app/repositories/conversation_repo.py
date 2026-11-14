from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Conversation
from app.db.models._common import utcnow


class ConversationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, user_id: int, title: str, knowledge_scope: str = "none") -> Conversation:
        conversation = Conversation(user_id=user_id, title=title, knowledge_scope=knowledge_scope)
        self.session.add(conversation)
        self.session.commit()
        self.session.refresh(conversation)
        return conversation

    def get_for_user(self, conversation_id: int, user_id: int) -> Conversation | None:
        return self.session.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        )

    def list_for_user(self, user_id: int) -> list[Conversation]:
        return list(
            self.session.scalars(
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            )
        )

    def update(self, conversation: Conversation, *, title: str | None = None) -> Conversation:
        if title is not None:
            conversation.title = title
        conversation.updated_at = utcnow()
        self.session.commit()
        self.session.refresh(conversation)
        return conversation
