from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pinecone import ServerlessSpec

from app.core.errors import VectorStoreUnavailableError
from app.rag.vectorstore.base import VectorMatch, VectorRecord
from app.rag.vectorstore.pinecone_store import PineconeVectorStore


def _store(has_index=True):
    client = MagicMock()
    client.has_index.return_value = has_index
    index = client.Index.return_value
    store = PineconeVectorStore(client, "idx", 1024, "aws", "us-east-1")
    return store, client, index


def test_ensure_index_creates_when_missing():
    store, client, _ = _store(has_index=False)
    store.ensure_index()
    kwargs = client.create_index.call_args.kwargs
    assert (kwargs["name"], kwargs["dimension"], kwargs["metric"]) == ("idx", 1024, "cosine")
    assert kwargs["spec"] == ServerlessSpec(cloud="aws", region="us-east-1")


def test_ensure_index_skips_when_present():
    store, client, _ = _store(has_index=True)
    store.ensure_index()
    client.create_index.assert_not_called()


def test_operations_ensure_index_once():
    store, client, index = _store(has_index=True)
    index.query.return_value = SimpleNamespace(matches=[])
    store.query("company", [0.1], 3)
    store.query("company", [0.1], 3)
    assert client.has_index.call_count == 1


def test_upsert_batches_of_100():
    store, _, index = _store()
    records = [VectorRecord(f"doc-1#{i}", [0.1], {"document_id": 1}) for i in range(250)]
    store.upsert("personal", records)
    sizes = [len(c.kwargs["vectors"]) for c in index.upsert.call_args_list]
    assert sizes == [100, 100, 50]
    first = index.upsert.call_args_list[0].kwargs
    assert first["namespace"] == "personal"
    assert first["vectors"][0] == {"id": "doc-1#0", "values": [0.1], "metadata": {"document_id": 1}}


def test_query_passes_namespace_filter_and_maps_matches():
    store, _, index = _store()
    index.query.return_value = SimpleNamespace(
        matches=[SimpleNamespace(id="doc-1#0", score=0.91, metadata={"text": "hi"})]
    )
    flt = {"owner_oid": {"$eq": "oid-a"}}
    assert store.query("personal", [0.1, 0.2], 5, flt) == [
        VectorMatch("doc-1#0", 0.91, {"text": "hi"})
    ]
    kwargs = index.query.call_args.kwargs
    assert kwargs == {
        "vector": [0.1, 0.2],
        "top_k": 5,
        "namespace": "personal",
        "filter": flt,
        "include_metadata": True,
    }


def test_query_without_filter_omits_it():
    store, _, index = _store()
    index.query.return_value = SimpleNamespace(matches=[])
    store.query("company", [0.1], 5)
    assert "filter" not in index.query.call_args.kwargs


def test_delete_by_prefix_deletes_each_page():
    store, _, index = _store()
    page1 = SimpleNamespace(vectors=[SimpleNamespace(id="doc-1#0"), SimpleNamespace(id="doc-1#1")])
    page2 = SimpleNamespace(vectors=[SimpleNamespace(id="doc-1#2")])
    index.list.return_value = iter([page1, page2])
    store.delete_by_prefix("personal", "doc-1#")
    assert index.list.call_args.kwargs == {"prefix": "doc-1#", "namespace": "personal"}
    assert [c.kwargs for c in index.delete.call_args_list] == [
        {"ids": ["doc-1#0", "doc-1#1"], "namespace": "personal"},
        {"ids": ["doc-1#2"], "namespace": "personal"},
    ]


def test_ping_true_and_false_never_raises():
    store, client, _ = _store()
    assert store.ping() is True
    client.describe_index.side_effect = RuntimeError("down")
    assert store.ping() is False


def test_sdk_error_mapped():
    store, _, index = _store()
    index.upsert.side_effect = RuntimeError("boom")
    with pytest.raises(VectorStoreUnavailableError):
        store.upsert("personal", [VectorRecord("a", [0.1], {})])


def test_failed_ensure_index_is_retried_later():
    store, client, index = _store()
    client.has_index.side_effect = [RuntimeError("down"), True]
    index.query.return_value = SimpleNamespace(matches=[])
    with pytest.raises(VectorStoreUnavailableError):
        store.query("company", [0.1], 1)
    assert store.query("company", [0.1], 1) == []


def test_delete_ids_in_batches():
    store, _, index = _store()
    store.delete_ids("personal", [f"doc-1#{i}" for i in range(1500)])
    sizes = [len(c.kwargs["ids"]) for c in index.delete.call_args_list]
    assert sizes == [1000, 500]
    assert all(c.kwargs["namespace"] == "personal" for c in index.delete.call_args_list)


def test_delete_ids_empty_is_noop():
    store, client, index = _store()
    store.delete_ids("personal", [])
    index.delete.assert_not_called()
