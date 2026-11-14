import pytest

from app.core.errors import LLMRateLimitError


@pytest.fixture
def conversation(client, auth_header):
    def create(scope: str = "none", headers=None) -> int:
        r = client.post(
            "/api/v1/conversations",
            json={"knowledge_scope": scope},
            headers=headers or auth_header(),
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]

    return create


def test_chat_requires_auth(client):
    assert client.get("/api/v1/conversations").status_code == 401
    assert client.post("/api/v1/conversations", json={}).status_code == 401


def test_create_list_send_flow(client, auth_header):
    h = auth_header()
    created = client.post("/api/v1/conversations", json={}, headers=h)
    assert created.status_code == 201
    body = created.json()
    assert (body["title"], body["knowledge_scope"]) == ("New chat", "none")

    sent = client.post(
        f"/api/v1/conversations/{body['id']}/messages", json={"content": "hi"}, headers=h
    )
    assert sent.status_code == 200
    assert (sent.json()["role"], sent.json()["content"], sent.json()["sources"]) == (
        "assistant",
        "Hello!",
        None,
    )

    history = client.get(f"/api/v1/conversations/{body['id']}/messages", headers=h).json()
    assert [m["role"] for m in history] == ["user", "assistant"]
    listed = client.get("/api/v1/conversations", headers=h).json()
    assert [(c["id"], c["title"]) for c in listed] == [(body["id"], "hi")]


def test_create_with_scope_and_invalid_scope(client, auth_header):
    r = client.post(
        "/api/v1/conversations", json={"knowledge_scope": "company"}, headers=auth_header()
    )
    assert r.json()["knowledge_scope"] == "company"
    r = client.post(
        "/api/v1/conversations", json={"knowledge_scope": "everything"}, headers=auth_header()
    )
    assert r.status_code == 422


def test_other_users_conversation_404(client, conversation, bob_header):
    cid = conversation()
    r = client.get(f"/api/v1/conversations/{cid}/messages", headers=bob_header)
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = client.post(
        f"/api/v1/conversations/{cid}/messages", json={"content": "hi"}, headers=bob_header
    )
    assert r.status_code == 404
    assert client.get("/api/v1/conversations", headers=bob_header).json() == []


def test_send_message_rejects_blank_and_oversized(client, conversation, auth_header, fake_llm):
    cid = conversation()
    for content in ["", "   \n ", "x" * 8001]:
        r = client.post(
            f"/api/v1/conversations/{cid}/messages",
            json={"content": content},
            headers=auth_header(),
        )
        assert r.status_code == 422, content
        assert r.json()["error"]["code"] == "validation_error"
    assert fake_llm.calls == []


def test_send_message_rate_limited_429(client, conversation, auth_header, fake_llm):
    cid = conversation()
    fake_llm.error = LLMRateLimitError("The AI service rate limit was reached.")
    r = client.post(
        f"/api/v1/conversations/{cid}/messages", json={"content": "hi"}, headers=auth_header()
    )
    assert r.status_code == 429 and r.json()["error"]["code"] == "llm_rate_limited"
    history = client.get(f"/api/v1/conversations/{cid}/messages", headers=auth_header())
    assert history.json() == []


def test_scoped_chat_502_when_vector_store_down(
    client, conversation, auth_header, fake_vector_store
):
    cid = conversation("personal")
    fake_vector_store.available = False
    r = client.post(
        f"/api/v1/conversations/{cid}/messages", json={"content": "hi"}, headers=auth_header()
    )
    assert r.status_code == 502 and r.json()["error"]["code"] == "vector_store_unavailable"


def test_scoped_chat_returns_sources(client, conversation, auth_header):
    upload = client.post(
        "/api/v1/documents",
        data={"scope": "personal"},
        files={"file": ("plan.txt", b"apollo sprint plan", "text/plain")},
        headers=auth_header(),
    )
    cid = conversation("personal")
    r = client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "apollo sprint plan"},
        headers=auth_header(),
    )
    assert r.json()["sources"] == [
        {"document_id": upload.json()["id"], "filename": "plan.txt", "page": None}
    ]


def test_stream_returns_text(client, conversation, auth_header, fake_llm):
    cid = conversation()
    fake_llm.chunks = ["Hel", "lo"]
    r = client.post(
        f"/api/v1/conversations/{cid}/messages/stream",
        json={"content": "hi"},
        headers=auth_header(),
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert r.text == "Hello"
    history = client.get(f"/api/v1/conversations/{cid}/messages", headers=auth_header()).json()
    assert [m["content"] for m in history] == ["hi", "Hello"]


def test_stream_rate_limited_before_first_chunk_returns_429(
    client, conversation, auth_header, fake_llm
):
    cid = conversation()
    fake_llm.error = LLMRateLimitError("rl")
    r = client.post(
        f"/api/v1/conversations/{cid}/messages/stream",
        json={"content": "hi"},
        headers=auth_header(),
    )
    assert r.status_code == 429 and r.json()["error"]["code"] == "llm_rate_limited"
