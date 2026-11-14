import time

from sqlalchemy import text

from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.user_repo import UserRepository


def _users(db_session):
    repo = UserRepository(db_session)
    return repo.upsert_from_identity("oid-a", "a@org", "A"), repo.upsert_from_identity(
        "oid-b", "b@org", "B"
    )


def test_get_for_user_hides_other_users_conversation(db_session):
    a, b = _users(db_session)
    repo = ConversationRepository(db_session)
    conv = repo.create(a.id, "mine")
    assert repo.get_for_user(conv.id, b.id) is None
    assert repo.get_for_user(conv.id, a.id).id == conv.id
    assert repo.get_for_user(9999, a.id) is None


def test_conversation_knowledge_scope_persisted(db_session):
    a, _ = _users(db_session)
    repo = ConversationRepository(db_session)
    assert repo.create(a.id, "plain").knowledge_scope == "none"
    conv = repo.create(a.id, "docs", "company")
    db_session.expire_all()
    assert repo.get_for_user(conv.id, a.id).knowledge_scope == "company"


def test_list_for_user_newest_first(db_session):
    a, b = _users(db_session)
    repo = ConversationRepository(db_session)
    old = repo.create(a.id, "old")
    time.sleep(0.01)
    new = repo.create(a.id, "new")
    repo.create(b.id, "bobs")
    assert [c.id for c in repo.list_for_user(a.id)] == [new.id, old.id]
    time.sleep(0.01)
    repo.update(old, title="renamed")
    listed = repo.list_for_user(a.id)
    assert [c.id for c in listed] == [old.id, new.id]
    assert listed[0].title == "renamed"


def test_deleting_conversation_cascades_messages(db_session):
    a, _ = _users(db_session)
    conversations = ConversationRepository(db_session)
    messages = MessageRepository(db_session)
    conv = conversations.create(a.id, "x")
    messages.add(conv.id, "user", "hi")
    db_session.execute(text("DELETE FROM conversations WHERE id = :id"), {"id": conv.id})
    db_session.commit()
    assert messages.list_for_conversation(conv.id) == []
