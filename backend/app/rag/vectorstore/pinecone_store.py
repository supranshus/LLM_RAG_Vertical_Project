import logging
import threading
import time
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from pinecone import ServerlessSpec

from app.core.errors import VectorStoreUnavailableError
from app.rag.vectorstore.base import VectorMatch, VectorRecord, VectorStore

logger = logging.getLogger(__name__)
T = TypeVar("T")

UPSERT_BATCH_SIZE = 100
DELETE_BATCH_SIZE = 1000


class PineconeVectorStore(VectorStore):
    """A Pinecone serverless index (cosine metric), created on first use if missing."""

    def __init__(self, client: Any, index_name: str, dimension: int, cloud: str, region: str):
        self.client = client
        self.index_name = index_name
        self.dimension = dimension
        self.cloud = cloud
        self.region = region
        self._index: Any = None
        self._lock = threading.Lock()

    def ensure_index(self) -> None:
        self._call("ensure_index", "-", 0, self._get_index)

    def upsert(self, namespace: str, records: Sequence[VectorRecord]) -> None:
        def run() -> None:
            index = self._get_index()
            for start in range(0, len(records), UPSERT_BATCH_SIZE):
                batch = records[start : start + UPSERT_BATCH_SIZE]
                index.upsert(
                    vectors=[
                        {"id": r.id, "values": r.values, "metadata": r.metadata} for r in batch
                    ],
                    namespace=namespace,
                )

        self._call("upsert", namespace, len(records), run)

    def query(
        self,
        namespace: str,
        vector: Sequence[float],
        top_k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        def run() -> list[VectorMatch]:
            kwargs: dict[str, Any] = {
                "vector": list(vector),
                "top_k": top_k,
                "namespace": namespace,
                "include_metadata": True,
            }
            if filter is not None:
                kwargs["filter"] = filter
            response = self._get_index().query(**kwargs)
            return [
                VectorMatch(m.id, float(m.score), dict(m.metadata or {})) for m in response.matches
            ]

        return self._call("query", namespace, top_k, run)

    def delete_ids(self, namespace: str, ids: Sequence[str]) -> None:
        if not ids:
            return

        def run() -> None:
            index = self._get_index()
            for start in range(0, len(ids), DELETE_BATCH_SIZE):
                index.delete(ids=list(ids[start : start + DELETE_BATCH_SIZE]), namespace=namespace)

        self._call("delete_ids", namespace, len(ids), run)

    def delete_by_prefix(self, namespace: str, prefix: str) -> None:
        def run() -> None:
            index = self._get_index()
            for page in index.list(prefix=prefix, namespace=namespace):
                ids = [item.id for item in page.vectors if item.id]
                if ids:
                    index.delete(ids=ids, namespace=namespace)

        self._call("delete_by_prefix", namespace, 0, run)

    def ping(self) -> bool:
        try:
            self.client.describe_index(self.index_name)
            return True
        except Exception:
            return False

    def _get_index(self) -> Any:
        with self._lock:
            if self._index is None:
                if not self.client.has_index(self.index_name):
                    logger.info("Creating Pinecone index %s", self.index_name)
                    self.client.create_index(
                        name=self.index_name,
                        dimension=self.dimension,
                        metric="cosine",
                        spec=ServerlessSpec(cloud=self.cloud, region=self.region),
                    )
                self._index = self.client.Index(name=self.index_name)
            return self._index

    def _call(self, op: str, namespace: str, count: int, fn: Callable[[], T]) -> T:
        start = time.perf_counter()
        ok = False
        try:
            result = fn()
            ok = True
            return result
        except Exception as exc:
            logger.warning("Pinecone %s failed: %s", op, type(exc).__name__)
            raise VectorStoreUnavailableError("Document search service is unavailable") from exc
        finally:
            logger.info(
                "vector op=%s namespace=%s count=%d latency_ms=%d ok=%s",
                op,
                namespace,
                count,
                (time.perf_counter() - start) * 1000,
                ok,
            )
