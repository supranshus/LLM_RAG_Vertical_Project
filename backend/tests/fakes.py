"""In-memory stand-ins for external services, so tests run offline."""

import math
import re
import zlib
from collections.abc import Iterator, Sequence
from typing import Any

from app.core.errors import LLMUnavailableError, VectorStoreUnavailableError
from app.llm.base import ChatMessage, LLMProvider, LLMResponse
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.vectorstore.base import VectorMatch, VectorRecord, VectorStore


class FakeLLMProvider(LLMProvider):
    name = "fake"
    default_model = "fake-model"

    def __init__(
        self,
        reply: str = "Hello!",
        chunks: list[str] | None = None,
        error: Exception | None = None,
        fail_after: int | None = None,
    ):
        self.reply = reply
        self.chunks = chunks
        self.error = error
        self.fail_after = fail_after
        self.calls: list[list[ChatMessage]] = []

    def chat(self, messages: Sequence[ChatMessage], **_kwargs) -> LLMResponse:
        self.calls.append(list(messages))
        if self.error:
            raise self.error
        return LLMResponse(self.reply, self.default_model, 5, 7)

    def stream_chat(self, messages: Sequence[ChatMessage], **_kwargs) -> Iterator[str]:
        self.calls.append(list(messages))
        if self.error:
            raise self.error
        return self._stream()

    def _stream(self) -> Iterator[str]:
        for i, chunk in enumerate(self.chunks if self.chunks is not None else [self.reply]):
            if self.fail_after is not None and i >= self.fail_after:
                raise LLMUnavailableError("stream broke")
            yield chunk


class FakeEmbeddingProvider(EmbeddingProvider):
    """Bag-of-words vectors: texts sharing words score high, unrelated texts near 0."""

    name = "fake"

    def __init__(self, dimension: int = 64, fail: bool = False):
        self.dimension = dimension
        self.fail = fail

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        if self.fail:
            raise VectorStoreUnavailableError("Document search service is unavailable")
        vector = [0.0] * self.dimension
        for word in re.findall(r"\w+", text.lower()):
            vector[zlib.crc32(word.encode()) % self.dimension] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class FakeVectorStore(VectorStore):
    def __init__(self):
        self.data: dict[str, dict[str, tuple[list[float], dict[str, Any]]]] = {}
        self.available = True
        self.lag_listing = False
        self.queries: list[tuple[str, dict[str, Any] | None]] = []

    def ensure_index(self) -> None:
        self._check()

    def upsert(self, namespace: str, records: Sequence[VectorRecord]) -> None:
        self._check()
        space = self.data.setdefault(namespace, {})
        for record in records:
            space[record.id] = (list(record.values), dict(record.metadata))

    def query(
        self,
        namespace: str,
        vector: Sequence[float],
        top_k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        self._check()
        self.queries.append((namespace, filter))
        matches = [
            VectorMatch(id_, _cosine(vector, values), metadata)
            for id_, (values, metadata) in self.data.get(namespace, {}).items()
            if _matches(metadata, filter)
        ]
        return sorted(matches, key=lambda m: m.score, reverse=True)[:top_k]

    def delete_ids(self, namespace: str, ids: Sequence[str]) -> None:
        self._check()
        space = self.data.get(namespace, {})
        for id_ in ids:
            space.pop(id_, None)

    def delete_by_prefix(self, namespace: str, prefix: str) -> None:
        self._check()
        if self.lag_listing:
            return  # like Pinecone serverless: listing hasn't caught up with recent writes
        space = self.data.get(namespace, {})
        for id_ in [i for i in space if i.startswith(prefix)]:
            del space[id_]

    def ping(self) -> bool:
        return self.available

    def ids(self, namespace: str) -> set[str]:
        return set(self.data.get(namespace, {}))

    def metadata(self, namespace: str, id_: str) -> dict[str, Any]:
        return self.data[namespace][id_][1]

    def _check(self) -> None:
        if not self.available:
            raise VectorStoreUnavailableError("Document search service is unavailable")


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norms = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norms if norms else 0.0


def _matches(metadata: dict[str, Any], filter: dict[str, Any] | None) -> bool:
    for key, condition in (filter or {}).items():
        expected = condition["$eq"] if isinstance(condition, dict) else condition
        if metadata.get(key) != expected:
            return False
    return True
