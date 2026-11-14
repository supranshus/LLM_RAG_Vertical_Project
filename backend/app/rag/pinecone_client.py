from functools import lru_cache

from pinecone import Pinecone


@lru_cache
def get_pinecone_client(api_key: str) -> Pinecone:
    """One shared client for both embeddings and the vector store."""
    return Pinecone(api_key=api_key)
