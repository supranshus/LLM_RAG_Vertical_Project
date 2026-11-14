from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Conversation, Message, User
from app.db.models._common import utcnow


@dataclass
class UserStats:
    user: User
    conversation_count: int
    message_count: int


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_oid(self, oid: str) -> User | None:
        return self.session.scalar(select(User).where(User.entra_oid == oid))

    def upsert_from_identity(self, oid: str, email: str, display_name: str) -> User:
        user = self.get_by_oid(oid)
        if user is None:
            user = User(entra_oid=oid, email=email, display_name=display_name)
            self.session.add(user)
        else:
            user.email = email
            user.display_name = display_name
            user.last_seen_at = utcnow()
        self.session.commit()
        self.session.refresh(user)
        return user

    def list_with_stats(self) -> list[UserStats]:
        conversation_counts = (
            select(Conversation.user_id, func.count(Conversation.id).label("n"))
            .group_by(Conversation.user_id)
            .subquery()
        )
        message_counts = (
            select(Conversation.user_id, func.count(Message.id).label("n"))
            .join(Message, Message.conversation_id == Conversation.id)
            .group_by(Conversation.user_id)
            .subquery()
        )
        rows = self.session.execute(
            select(
                User,
                func.coalesce(conversation_counts.c.n, 0),
                func.coalesce(message_counts.c.n, 0),
            )
            .outerjoin(conversation_counts, conversation_counts.c.user_id == User.id)
            .outerjoin(message_counts, message_counts.c.user_id == User.id)
            .order_by(User.last_seen_at.desc(), User.id.desc())
        ).all()
        return [UserStats(user, conversations, messages) for user, conversations, messages in rows]
