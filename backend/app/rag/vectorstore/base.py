from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VectorRecord:
    id: str
    values: list[float]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class VectorMatch:
    id: str
    score: float
    metadata: dict[str, Any]


class VectorStore(ABC):
    """Stores and searches vectors. Failures surface as VectorStoreUnavailableError."""

    @abstractmethod
    def ensure_index(self) -> None:
        """Create the index if it does not exist yet."""

    @abstractmethod
    def upsert(self, namespace: str, records: Sequence[VectorRecord]) -> None: ...

    @abstractmethod
    def query(
        self,
        namespace: str,
        vector: Sequence[float],
        top_k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]: ...

    @abstractmethod
    def delete_ids(self, namespace: str, ids: Sequence[str]) -> None:
        """Delete these exact vectors. Missing ids are ignored."""

    @abstractmethod
    def delete_by_prefix(self, namespace: str, prefix: str) -> None:
        """Delete vectors whose id starts with prefix.

        Relies on listing, which may lag just-written vectors on eventually consistent
        stores; prefer delete_ids when the ids are known and use this as a backstop.
        """

    @abstractmethod
    def ping(self) -> bool:
        """True when the store is reachable. Never raises."""
