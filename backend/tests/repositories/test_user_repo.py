from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.user_repo import UserRepository


def test_upsert_creates_then_updates(db_session):
    repo = UserRepository(db_session)
    first = repo.upsert_from_identity("oid-1", "a@org", "A")
    second = repo.upsert_from_identity("oid-1", "a2@org", "A Two")
    assert first.id == second.id
    assert (second.email, second.display_name) == ("a2@org", "A Two")
    assert second.last_seen_at is not None


def test_get_by_oid(db_session):
    repo = UserRepository(db_session)
    assert repo.get_by_oid("missing") is None
    created = repo.upsert_from_identity("oid-1", "a@org", "A")
    assert repo.get_by_oid("oid-1").id == created.id


def test_list_with_stats_counts(db_session):
    users = UserRepository(db_session)
    conversations = ConversationRepository(db_session)
    messages = MessageRepository(db_session)
    a = users.upsert_from_identity("oid-a", "a@org", "A")
    users.upsert_from_identity("oid-b", "b@org", "B")
    c1 = conversations.create(a.id, "one")
    c2 = conversations.create(a.id, "two")
    messages.add(c1.id, "user", "hi")
    messages.add(c1.id, "assistant", "hello")
    messages.add(c2.id, "user", "again")

    stats = {s.user.entra_oid: s for s in users.list_with_stats()}
    assert (stats["oid-a"].conversation_count, stats["oid-a"].message_count) == (2, 3)
    assert (stats["oid-b"].conversation_count, stats["oid-b"].message_count) == (0, 0)
