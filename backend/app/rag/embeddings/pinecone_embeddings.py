import logging
import time
from collections.abc import Sequence
from typing import Any

from app.core.errors import VectorStoreUnavailableError
from app.rag.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class PineconeEmbeddingProvider(EmbeddingProvider):
    """Embeddings from Pinecone's hosted inference models."""

    name = "pinecone"

    def __init__(self, client: Any, model: str, dimension: int, batch_size: int = 96):
        self.client = client
        self.model = model
        self.dimension = dimension
        self.batch_size = batch_size

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(self._embed(texts[start : start + self.batch_size], "passage"))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "query")[0]

    def _embed(self, texts: Sequence[str], input_type: str) -> list[list[float]]:
        start = time.perf_counter()
        ok = False
        try:
            result = self.client.inference.embed(
                model=self.model,
                inputs=list(texts),
                parameters={"input_type": input_type, "truncate": "END"},
            )
            vectors = [list(item.values) for item in result]
            ok = True
            return vectors
        except Exception as exc:
            raise VectorStoreUnavailableError("Document search service is unavailable") from exc
        finally:
            logger.info(
                "embed provider=pinecone model=%s count=%d latency_ms=%d ok=%s",
                self.model,
                len(texts),
                (time.perf_counter() - start) * 1000,
                ok,
            )
