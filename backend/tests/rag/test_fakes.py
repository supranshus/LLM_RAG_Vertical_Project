import pytest

from app.core.errors import VectorStoreUnavailableError
from app.rag.vectorstore.base import VectorRecord
from tests.fakes import FakeEmbeddingProvider, FakeVectorStore


def test_fake_store_honours_filter_and_ranking():
    store, embed = FakeVectorStore(), FakeEmbeddingProvider()
    store.upsert(
        "personal",
        [
            VectorRecord("a", embed.embed_query("sprint plan"), {"owner_oid": "A"}),
            VectorRecord("b", embed.embed_query("sprint plan"), {"owner_oid": "B"}),
            VectorRecord("c", embed.embed_query("holiday photos"), {"owner_oid": "A"}),
        ],
    )
    hits = store.query("personal", embed.embed_query("sprint plan"), 5, {"owner_oid": {"$eq": "A"}})
    assert [h.id for h in hits] == ["a", "c"]
    assert hits[0].score > 0.99 and hits[1].score < 0.5
    assert store.queries[-1] == ("personal", {"owner_oid": {"$eq": "A"}})


def test_fake_store_delete_by_prefix_and_unavailable():
    store = FakeVectorStore()
    store.upsert(
        "company", [VectorRecord("doc-1#0", [1.0], {}), VectorRecord("doc-2#0", [1.0], {})]
    )
    store.delete_by_prefix("company", "doc-1#")
    assert store.ids("company") == {"doc-2#0"}
    store.available = False
    assert store.ping() is False
    with pytest.raises(VectorStoreUnavailableError):
        store.query("company", [1.0], 1)


def test_fake_embeddings_failure_flag():
    with pytest.raises(VectorStoreUnavailableError):
        FakeEmbeddingProvider(fail=True).embed_documents(["x"])


def test_fake_store_delete_ids_and_lagging_list():
    store = FakeVectorStore()
    store.upsert(
        "company", [VectorRecord("doc-1#0", [1.0], {}), VectorRecord("doc-1#1", [1.0], {})]
    )
    store.lag_listing = True
    store.delete_by_prefix("company", "doc-1#")  # listing doesn't see the new ids yet
    assert store.ids("company") == {"doc-1#0", "doc-1#1"}
    store.delete_ids("company", ["doc-1#0", "doc-1#1", "missing"])
    assert store.ids("company") == set()
