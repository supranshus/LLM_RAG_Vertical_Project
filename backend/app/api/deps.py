from collections.abc import Callable, Iterator
from functools import lru_cache

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.logging import user_var
from app.core.security import CurrentUser, TokenValidator
from app.db.base import get_sessionmaker
from app.llm.base import LLMProvider
from app.llm.factory import get_llm_provider
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.embeddings.factory import get_embedding_provider
from app.rag.storage import FileStorage
from app.rag.vectorstore.base import VectorStore
from app.rag.vectorstore.factory import get_vector_store as build_vector_store
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.health_repo import HealthRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.user_repo import UserRepository
from app.services.admin_service import AdminService
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService
from app.services.health_service import HealthService
from app.services.retrieval_service import RetrievalService
from app.services.user_service import UserService

_bearer = HTTPBearer(auto_error=False)


def get_session_factory() -> sessionmaker[Session]:
    return get_sessionmaker()


def get_db(factory: sessionmaker[Session] = Depends(get_session_factory)) -> Iterator[Session]:
    session = factory()
    try:
        yield session
    finally:
        session.close()


@lru_cache
def get_token_validator() -> TokenValidator:
    settings = get_settings()
    return TokenValidator(
        settings.entra_tenant_id,
        settings.entra_client_id,
        required_scope=settings.entra_required_scope,
    )


@lru_cache
def get_llm() -> LLMProvider:
    return get_llm_provider(get_settings())


@lru_cache
def get_embeddings() -> EmbeddingProvider:
    return get_embedding_provider(get_settings())


@lru_cache
def get_vector_store() -> VectorStore:
    return build_vector_store(get_settings())


@lru_cache
def get_file_storage() -> FileStorage:
    return FileStorage(get_settings().upload_dir)


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(UserRepository(db))


def get_retrieval_service(
    embeddings: EmbeddingProvider = Depends(get_embeddings),
    vector_store: VectorStore = Depends(get_vector_store),
) -> RetrievalService:
    settings = get_settings()
    return RetrievalService(embeddings, vector_store, settings.rag_top_k, settings.rag_min_score)


def get_session_closer(db: Session = Depends(get_db)) -> Callable[[], None]:
    """Lets a streaming route release the request's session once its body is sent."""
    return db.close


def get_health_service(
    db: Session = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store),
) -> HealthService:
    return HealthService(HealthRepository(db), vector_store)


def get_admin_service(db: Session = Depends(get_db)) -> AdminService:
    return AdminService(UserRepository(db))


def get_chat_service(
    db: Session = Depends(get_db),
    llm: LLMProvider = Depends(get_llm),
    retrieval: RetrievalService = Depends(get_retrieval_service),
) -> ChatService:
    settings = get_settings()
    return ChatService(
        ConversationRepository(db),
        MessageRepository(db),
        llm,
        retrieval,
        system_prompt=settings.chat_system_prompt,
        history_limit=settings.chat_history_limit,
    )


def build_document_service(
    session: Session,
    storage: FileStorage,
    embeddings: EmbeddingProvider,
    vector_store: VectorStore,
) -> DocumentService:
    settings = get_settings()
    return DocumentService(
        DocumentRepository(session),
        storage,
        embeddings,
        vector_store,
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
        max_upload_bytes=settings.max_upload_mb * 1024 * 1024,
    )


def get_document_service(
    db: Session = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
    embeddings: EmbeddingProvider = Depends(get_embeddings),
    vector_store: VectorStore = Depends(get_vector_store),
) -> DocumentService:
    return build_document_service(db, storage, embeddings, vector_store)


def get_document_processor(
    factory: sessionmaker[Session] = Depends(get_session_factory),
    storage: FileStorage = Depends(get_file_storage),
    embeddings: EmbeddingProvider = Depends(get_embeddings),
    vector_store: VectorStore = Depends(get_vector_store),
) -> Callable[[int], None]:
    """A background job that processes one document in its own database session.

    The request's session is closed by the time background tasks run.
    """

    def process(document_id: int) -> None:
        with factory() as session:
            build_document_service(session, storage, embeddings, vector_store).process(document_id)

    return process


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    validator: TokenValidator = Depends(get_token_validator),
    users: UserService = Depends(get_user_service),
) -> CurrentUser:
    # Async on purpose: blocking work runs in the threadpool, and setting user_var here
    # (in the request's own context) makes the user visible to every later log line.
    if credentials is None:
        raise UnauthorizedError("Missing bearer token")
    claims = await run_in_threadpool(validator.validate, credentials.credentials)
    user = await run_in_threadpool(users.sync_user, claims)
    user_var.set(user.email)
    return user


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_admin:
        raise ForbiddenError("Admin role required")
    return user
