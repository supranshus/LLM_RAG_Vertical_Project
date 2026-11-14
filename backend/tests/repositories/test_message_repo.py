from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.user_repo import UserRepository


def _conversation(db_session):
    user = UserRepository(db_session).upsert_from_identity("oid-a", "a@org", "A")
    return ConversationRepository(db_session).create(user.id, "x")


def test_list_for_conversation_limit_returns_last_n_chronological(db_session):
    conv = _conversation(db_session)
    repo = MessageRepository(db_session)
    for i in range(1, 6):
        repo.add(conv.id, "user", f"m{i}")
    assert [m.content for m in repo.list_for_conversation(conv.id)] == [
        "m1",
        "m2",
        "m3",
        "m4",
        "m5",
    ]
    assert [m.content for m in repo.list_for_conversation(conv.id, limit=2)] == ["m4", "m5"]


def test_message_fields_and_sources_round_trip(db_session):
    conv = _conversation(db_session)
    repo = MessageRepository(db_session)
    sources = [{"document_id": 1, "filename": "a.pdf", "page": 2}]
    repo.add(
        conv.id,
        "assistant",
        "answer",
        model="m",
        prompt_tokens=3,
        completion_tokens=4,
        sources=sources,
    )
    repo.add(conv.id, "user", "plain")
    db_session.expire_all()
    saved, plain = repo.list_for_conversation(conv.id)
    assert (saved.model, saved.prompt_tokens, saved.completion_tokens) == ("m", 3, 4)
    assert saved.sources == sources
    assert plain.sources is None
