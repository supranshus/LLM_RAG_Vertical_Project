import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from app.api import deps
from app.api.v1.routes import admin, chat, documents, health, me
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.rag.vectorstore.base import VectorStore
from app.repositories.document_repo import DocumentRepository
from app.services.document_service import INTERRUPTED_MESSAGE

logger = logging.getLogger(__name__)


def fail_interrupted_documents(session_factory: sessionmaker[Session]) -> None:
    """Documents left 'processing' by a restart will never finish; mark them failed."""
    with session_factory() as session:
        count = DocumentRepository(session).fail_all_processing(INTERRUPTED_MESSAGE)
    if count:
        logger.warning("Marked %d interrupted document(s) as failed", count)


def prepare_vector_store(vector_store: VectorStore) -> None:
    """Create the vector index if needed. Never raises: the API must start without it."""
    try:
        vector_store.ensure_index()
        logger.info("Vector store ready")
    except Exception as exc:
        logger.error("Vector store not ready: %s", exc)


def run_startup_tasks(session_factory: sessionmaker[Session], vector_store: VectorStore) -> None:
    fail_interrupted_documents(session_factory)
    prepare_vector_store(vector_store)


def create_app(run_startup: bool = True) -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_dir, settings.log_level, "backend.log", settings.log_retention_days)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if run_startup:
            await run_in_threadpool(fail_interrupted_documents, deps.get_session_factory())
            # Creating a Pinecone index can take a while; don't hold up startup for it.
            threading.Thread(
                target=prepare_vector_store, args=(deps.get_vector_store(),), daemon=True
            ).start()
        yield

    app = FastAPI(title="GenAI Boilerplate API", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(chat.router)
    app.include_router(documents.router)
    app.include_router(admin.router)
    return app


app = create_app()
