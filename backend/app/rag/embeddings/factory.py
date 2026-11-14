from collections.abc import Callable

from app.core.config import Settings
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.embeddings.pinecone_embeddings import PineconeEmbeddingProvider
from app.rag.pinecone_client import get_pinecone_client


def _build_pinecone(settings: Settings) -> EmbeddingProvider:
    return PineconeEmbeddingProvider(
        get_pinecone_client(settings.pinecone_api_key.get_secret_value()),
        model=settings.embedding_model,
        dimension=settings.embedding_dimension,
    )


# To add a provider: implement EmbeddingProvider, add a builder here, set EMBEDDING_PROVIDER.
_PROVIDERS: dict[str, Callable[[Settings], EmbeddingProvider]] = {
    "pinecone": _build_pinecone,
}


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    name = settings.embedding_provider.lower()
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown EMBEDDING_PROVIDER: {name!r}")
    return _PROVIDERS[name](settings)
