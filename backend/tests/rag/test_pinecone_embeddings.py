from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.errors import VectorStoreUnavailableError
from app.rag.embeddings.pinecone_embeddings import PineconeEmbeddingProvider


def _client():
    client = MagicMock()
    client.inference.embed.side_effect = lambda model, inputs, parameters: [
        SimpleNamespace(values=[float(len(text)), 1.0]) for text in inputs
    ]
    return client


def test_embed_documents_batches_and_passage_mode():
    client = _client()
    provider = PineconeEmbeddingProvider(client, "multilingual-e5-large", 1024, batch_size=96)
    vectors = provider.embed_documents([f"t{i}" for i in range(200)])
    calls = client.inference.embed.call_args_list
    assert [len(c.kwargs["inputs"]) for c in calls] == [96, 96, 8]
    assert all(
        c.kwargs["parameters"] == {"input_type": "passage", "truncate": "END"} for c in calls
    )
    assert all(c.kwargs["model"] == "multilingual-e5-large" for c in calls)
    assert len(vectors) == 200 and vectors[0] == [2.0, 1.0]


def test_embed_documents_empty_makes_no_call():
    client = _client()
    assert PineconeEmbeddingProvider(client, "m", 2).embed_documents([]) == []
    client.inference.embed.assert_not_called()


def test_embed_query_uses_query_mode():
    client = _client()
    provider = PineconeEmbeddingProvider(client, "m", 2)
    assert provider.embed_query("abc") == [3.0, 1.0]
    assert client.inference.embed.call_args.kwargs["parameters"]["input_type"] == "query"
    assert provider.dimension == 2


def test_embed_error_mapped():
    client = MagicMock()
    client.inference.embed.side_effect = RuntimeError("429 too many requests")
    with pytest.raises(VectorStoreUnavailableError):
        PineconeEmbeddingProvider(client, "m", 2).embed_query("x")
