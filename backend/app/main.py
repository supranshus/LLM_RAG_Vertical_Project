import logging
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2AuthorizationCodeBearer
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

    # Docs only: adds an Entra sign-in to the Authorize dialog in Swagger UI (/swagger).
    # It never rejects a request; deps.get_current_user still validates every token.
    entra = f"https://login.microsoftonline.com/{settings.entra_tenant_id}/oauth2/v2.0"
    scope = f"api://{settings.entra_client_id}/{settings.entra_required_scope}"
    swagger_sign_in = OAuth2AuthorizationCodeBearer(
        authorizationUrl=f"{entra}/authorize",
        tokenUrl=f"{entra}/token",
        scopes={scope: "Use the API as the signed-in user"},
        auto_error=False,
    )

    app = FastAPI(
        title="AI Powered Project Management Platform",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/swagger",
        dependencies=[Depends(swagger_sign_in)],
        swagger_ui_init_oauth={
            "clientId": settings.entra_client_id,
            "scopes": scope,
            "usePkceWithAuthorizationCodeGrant": True,
        },
    )
    register_exception_handlers(app)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(chat.router)
    app.include_router(documents.router)
    app.include_router(admin.router)

    @app.get("/", include_in_schema=False)
    def open_swagger() -> RedirectResponse:
        return RedirectResponse("/swagger")

    return app


app = create_app()
