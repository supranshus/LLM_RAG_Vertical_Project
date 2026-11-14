from abc import ABC, abstractmethod
from collections.abc import Sequence


class EmbeddingProvider(ABC):
    """Turns text into vectors. Failures surface as VectorStoreUnavailableError."""

    name: str
    dimension: int

    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Vectors for passages being stored."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Vector for a search question."""
