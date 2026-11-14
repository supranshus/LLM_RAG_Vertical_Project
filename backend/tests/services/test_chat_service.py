from types import SimpleNamespace

import pytest

from app.core.errors import LLMRateLimitError, NotFoundError, VectorStoreUnavailableError
from app.llm.base import ChatMessage
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.services.chat_service import RAG_INSTRUCTIONS, ChatService
from tests.fakes import FakeLLMProvider

INTERRUPTED = "\n\n[Response interrupted. Please try again.]"


@pytest.fixture
def svc_factory(db_session, retrieval):
    def build(history_limit: int = 20, **llm_kwargs):
        llm = FakeLLMProvider(**llm_kwargs)
        service = ChatService(
            ConversationRepository(db_session),
            MessageRepository(db_session),
            llm,
            retrieval,
            system_prompt="SYS",
            history_limit=history_limit,
        )
        return service, llm

    return build


@pytest.fixture
def indexed_docs(alice, bob, index_text):
    return SimpleNamespace(
        alice_id=index_text(alice, "personal", "alice.txt", "apollo sprint plan"),
        bob_id=index_text(bob, "personal", "bob.txt", "apollo sprint plan"),
    )


def test_send_message_persists_exchange_and_titles(svc_factory, alice):
    svc, _ = svc_factory(reply="Hi Alice")
    conv = svc.create_conversation(alice)
    assert (conv.title, conv.knowledge_scope) == ("New chat", "none")

    reply = svc.send_message(alice, conv.id, "Plan my sprint\nplease")

    assert (reply.role, reply.content, reply.model, reply.sources) == (
        "assistant",
        "Hi Alice",
        "fake-model",
        None,
    )
    assert (reply.prompt_tokens, reply.completion_tokens) == (5, 7)
    assert [(m.role, m.content) for m in svc.get_messages(alice, conv.id)] == [
        ("user", "Plan my sprint\nplease"),
        ("assistant", "Hi Alice"),
    ]
    assert svc.list_conversations(alice)[0].title == "Plan my sprint please"


def test_title_truncated_to_60_and_kept_after_first_exchange(svc_factory, alice):
    svc, _ = svc_factory()
    conv = svc.create_conversation(alice)
    svc.send_message(alice, conv.id, "x" * 100)
    svc.send_message(alice, conv.id, "second question")
    assert svc.list_conversations(alice)[0].title == "x" * 60


def test_custom_title_not_replaced(svc_factory, alice):
    svc, _ = svc_factory()
    conv = svc.create_conversation(alice, title="My title")
    svc.send_message(alice, conv.id, "hello")
    assert svc.list_conversations(alice)[0].title == "My title"


def test_context_has_system_prompt_and_last_n(svc_factory, alice):
    svc, llm = svc_factory(history_limit=2)
    conv = svc.create_conversation(alice)
    for i in range(3):
        svc.send_message(alice, conv.id, f"q{i}")
    svc.send_message(alice, conv.id, "new")
    sent = llm.calls[-1]
    assert sent[0] == ChatMessage("system", "SYS")
    assert len(sent) == 1 + 2 + 1
    assert [m.content for m in sent[1:]] == ["q2", "Hello!", "new"]


def test_other_users_conversation_not_found(svc_factory, alice, bob):
    svc, _ = svc_factory()
    conv = svc.create_conversation(alice)
    with pytest.raises(NotFoundError):
        svc.get_messages(bob, conv.id)
    with pytest.raises(NotFoundError):
        svc.send_message(bob, conv.id, "hi")
    with pytest.raises(NotFoundError):
        svc.start_stream(bob, conv.id, "hi")
    assert svc.list_conversations(bob) == []


def test_send_message_rate_limited_persists_nothing(svc_factory, alice):
    svc, _ = svc_factory(error=LLMRateLimitError("rl"))
    conv = svc.create_conversation(alice)
    with pytest.raises(LLMRateLimitError):
        svc.send_message(alice, conv.id, "hi")
    assert svc.get_messages(alice, conv.id) == []


def test_personal_scoped_chat_uses_own_docs_with_sources(svc_factory, alice, indexed_docs):
    svc, llm = svc_factory()
    conv = svc.create_conversation(alice, knowledge_scope="personal")
    reply = svc.send_message(alice, conv.id, "apollo sprint plan")
    system = llm.calls[-1][0].content
    assert system.startswith("SYS\n\n" + RAG_INSTRUCTIONS)
    assert "[1] (alice.txt)\napollo sprint plan" in system
    assert "bob.txt" not in system
    assert reply.sources == [
        {"document_id": indexed_docs.alice_id, "filename": "alice.txt", "page": None}
    ]


def test_company_scoped_chat_uses_company_docs(svc_factory, alice, admin, index_text):
    doc_id = index_text(admin, "company", "handbook.txt", "leave policy twenty days")
    svc, llm = svc_factory()
    conv = svc.create_conversation(alice, knowledge_scope="company")
    reply = svc.send_message(alice, conv.id, "leave policy days")
    assert "[1] (handbook.txt)" in llm.calls[-1][0].content
    assert reply.sources == [{"document_id": doc_id, "filename": "handbook.txt", "page": None}]


def test_scoped_chat_no_match_still_answers(svc_factory, alice, indexed_docs):
    svc, llm = svc_factory(reply="I don't know")
    conv = svc.create_conversation(alice, knowledge_scope="personal")
    reply = svc.send_message(alice, conv.id, "holiday photos beach")
    assert "No documents matched this question." in llm.calls[-1][0].content
    assert (reply.content, reply.sources) == ("I don't know", [])


def test_scoped_chat_vector_store_down_persists_nothing(svc_factory, alice, fake_vector_store):
    svc, llm = svc_factory()
    conv = svc.create_conversation(alice, knowledge_scope="personal")
    fake_vector_store.available = False
    with pytest.raises(VectorStoreUnavailableError):
        svc.send_message(alice, conv.id, "anything")
    with pytest.raises(VectorStoreUnavailableError):
        svc.start_stream(alice, conv.id, "anything")
    assert svc.get_messages(alice, conv.id) == []
    assert llm.calls == []


def test_unscoped_chat_works_when_vector_store_down(svc_factory, alice, fake_vector_store):
    svc, _ = svc_factory()
    fake_vector_store.available = False
    conv = svc.create_conversation(alice)
    assert svc.send_message(alice, conv.id, "hi").content == "Hello!"


def test_stream_completes_and_persists_sources(svc_factory, alice, indexed_docs):
    svc, _ = svc_factory(chunks=["Hel", "lo"])
    conv = svc.create_conversation(alice, knowledge_scope="personal")
    assert "".join(svc.start_stream(alice, conv.id, "apollo sprint plan")) == "Hello"
    user_msg, reply = svc.get_messages(alice, conv.id)
    assert (user_msg.content, reply.content, reply.model) == (
        "apollo sprint plan",
        "Hello",
        "fake-model",
    )
    assert reply.sources == [
        {"document_id": indexed_docs.alice_id, "filename": "alice.txt", "page": None}
    ]
    assert svc.list_conversations(alice)[0].title == "apollo sprint plan"


def test_stream_unscoped_saves_no_sources(svc_factory, alice):
    svc, _ = svc_factory(chunks=["Hi"])
    conv = svc.create_conversation(alice)
    "".join(svc.start_stream(alice, conv.id, "hello"))
    assert svc.get_messages(alice, conv.id)[-1].sources is None


def test_stream_error_before_first_chunk_raises_eagerly_and_persists_nothing(svc_factory, alice):
    svc, _ = svc_factory(error=LLMRateLimitError("rl"))
    conv = svc.create_conversation(alice)
    with pytest.raises(LLMRateLimitError):
        svc.start_stream(alice, conv.id, "hi")  # raises before any iteration
    assert svc.get_messages(alice, conv.id) == []


def test_stream_interrupted_mid_reply(svc_factory, alice):
    svc, _ = svc_factory(chunks=["Par", "tial", "x"], fail_after=2)
    conv = svc.create_conversation(alice)
    assert "".join(svc.start_stream(alice, conv.id, "hi")) == "Partial" + INTERRUPTED
    assert [m.role for m in svc.get_messages(alice, conv.id)] == ["user"]


def test_stream_failing_on_first_chunk_raises_eagerly(svc_factory, alice):
    svc, _ = svc_factory(chunks=["never"], fail_after=0)
    conv = svc.create_conversation(alice)
    with pytest.raises(Exception, match="stream broke"):
        svc.start_stream(alice, conv.id, "hi")
    assert svc.get_messages(alice, conv.id) == []


def test_empty_stream_saves_empty_reply(svc_factory, alice):
    svc, _ = svc_factory(chunks=[])
    conv = svc.create_conversation(alice)
    assert "".join(svc.start_stream(alice, conv.id, "hi")) == ""
    assert [(m.role, m.content) for m in svc.get_messages(alice, conv.id)] == [
        ("user", "hi"),
        ("assistant", ""),
    ]


def test_stream_unexpected_error_mid_reply_still_ends_with_notice(svc_factory, alice):
    svc, llm = svc_factory()

    def broken(*_args, **_kwargs):
        yield "Par"
        raise RuntimeError("something unexpected")

    llm.stream_chat = broken
    conv = svc.create_conversation(alice)
    assert "".join(svc.start_stream(alice, conv.id, "hi")) == "Par" + INTERRUPTED
    assert [m.role for m in svc.get_messages(alice, conv.id)] == ["user"]
