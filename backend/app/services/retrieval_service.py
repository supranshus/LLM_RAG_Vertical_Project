from dataclasses import dataclass
from typing import Any

from app.core.security import CurrentUser
from app.core.types import DocumentScope
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.vectorstore.base import VectorStore


def vector_location(scope: DocumentScope, owner_oid: str) -> tuple[str, dict[str, Any] | None]:
    """Namespace and filter for a collection. The only place these are decided.

    Personal documents share one namespace, so every personal query MUST carry the
    owner filter; it is always built here from the signed-in user, never from input.
    """
    if scope == "personal":
        return "personal", {"owner_oid": {"$eq": owner_oid}}
    return "company", None


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: int
    filename: str
    page: int | None
    text: str
    score: float


class RetrievalService:
    """Finds the document passages most relevant to a question. Reusable by any feature."""

    def __init__(
        self,
        embeddings: EmbeddingProvider,
        vector_store: VectorStore,
        top_k: int,
        min_score: float,
    ):
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.top_k = top_k
        self.min_score = min_score

    def search(
        self,
        user: CurrentUser,
        scope: DocumentScope,
        query: str,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        namespace, filter_ = vector_location(scope, user.entra_oid)
        vector = self.embeddings.embed_query(query)
        matches = self.vector_store.query(namespace, vector, top_k or self.top_k, filter_)
        return [
            RetrievedChunk(
                document_id=int(match.metadata["document_id"]),
                filename=str(match.metadata.get("filename", "")),
                page=int(match.metadata["page"])
                if match.metadata.get("page") is not None
                else None,
                text=str(match.metadata.get("text", "")),
                score=match.score,
            )
            for match in matches
            if match.score >= self.min_score
        ]
