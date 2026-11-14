from collections.abc import Callable

from app.core.config import Settings
from app.rag.pinecone_client import get_pinecone_client
from app.rag.vectorstore.base import VectorStore
from app.rag.vectorstore.pinecone_store import PineconeVectorStore


def _build_pinecone(settings: Settings) -> VectorStore:
    return PineconeVectorStore(
        get_pinecone_client(settings.pinecone_api_key.get_secret_value()),
        index_name=settings.pinecone_index_name,
        dimension=settings.embedding_dimension,
        cloud=settings.pinecone_cloud,
        region=settings.pinecone_region,
    )


# To add a store: implement VectorStore, add a builder here, set VECTOR_STORE_PROVIDER.
_STORES: dict[str, Callable[[Settings], VectorStore]] = {
    "pinecone": _build_pinecone,
}


def get_vector_store(settings: Settings) -> VectorStore:
    name = settings.vector_store_provider.lower()
    if name not in _STORES:
        raise ValueError(f"Unknown VECTOR_STORE_PROVIDER: {name!r}")
    return _STORES[name](settings)
