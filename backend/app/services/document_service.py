import logging
import time
from pathlib import PurePosixPath, PureWindowsPath

from app.core.errors import (
    FileTooLargeError,
    ForbiddenError,
    NotFoundError,
    UnsupportedFileTypeError,
    VectorStoreUnavailableError,
)
from app.core.security import CurrentUser
from app.core.types import DocumentScope
from app.db.models import Document
from app.rag.chunking import chunk_pages
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.parsing import SUPPORTED_EXTENSIONS, DocumentParseError, parse_document
from app.rag.storage import FileStorage
from app.rag.vectorstore.base import VectorRecord, VectorStore
from app.repositories.document_repo import DocumentRepository
from app.services.retrieval_service import vector_location

logger = logging.getLogger(__name__)

NO_TEXT_MESSAGE = "No text found in this file (scanned PDFs are not supported)"
VECTOR_DOWN_MESSAGE = "Document search service is unavailable; please try again later"
INTERRUPTED_MESSAGE = "Processing was interrupted; please upload again"


class DocumentService:
    def __init__(
        self,
        documents: DocumentRepository,
        storage: FileStorage,
        embeddings: EmbeddingProvider,
        vector_store: VectorStore,
        chunk_size: int,
        chunk_overlap: int,
        max_upload_bytes: int,
    ):
        self.documents = documents
        self.storage = storage
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_upload_bytes = max_upload_bytes

    def upload(
        self,
        user: CurrentUser,
        scope: DocumentScope,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> Document:
        """Validate and store a file. Text extraction happens later in `process`."""
        if scope == "company" and not user.is_admin:
            raise ForbiddenError("Only admins can manage company documents")
        display_name = _base_name(filename)
        extension = PurePosixPath(display_name).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFileTypeError("Supported file types: PDF, DOCX, TXT, MD")
        if len(data) > self.max_upload_bytes:
            limit_mb = self.max_upload_bytes // (1024 * 1024)
            raise FileTooLargeError(f"File is larger than {limit_mb} MB")

        stored_name = self.storage.save(data, extension)
        document = self.documents.create(
            scope=scope,
            owner_user_id=user.id,
            filename=display_name,
            content_type=content_type or "application/octet-stream",
            size_bytes=len(data),
            storage_path=stored_name,
        )
        logger.info("Document %s uploaded scope=%s bytes=%d", document.id, scope, len(data))
        return document

    def process(self, document_id: int) -> None:
        """Extract, chunk, embed and index a document. Never raises."""
        start = time.perf_counter()
        document = self.documents.get(document_id)
        if document is None:
            return  # deleted before processing started; nothing was indexed
        prefix = f"doc-{document_id}#"
        # Owner comes from the row itself, never from the caller.
        owner_oid = self.documents.get_owner_oid(document)
        namespace, _ = vector_location(document.scope, owner_oid)
        written: list[str] = []
        try:
            extension = PurePosixPath(document.storage_path).suffix
            pages = parse_document(self.storage.path(document.storage_path), extension)
            chunks = chunk_pages(pages, self.chunk_size, self.chunk_overlap)
            if not chunks:
                self.documents.mark_failed(document, NO_TEXT_MESSAGE)
                logger.info("Document %s has no extractable text", document_id)
                return

            vectors = self.embeddings.embed_documents([c.text for c in chunks])
            records = [
                VectorRecord(
                    f"{prefix}{chunk.index}",
                    values,
                    _chunk_metadata(document, owner_oid, chunk.index, chunk.page, chunk.text),
                )
                for chunk, values in zip(chunks, vectors, strict=True)
            ]
            written = [record.id for record in records]
            self.vector_store.upsert(namespace, records)

            if not self.documents.mark_ready_if_processing(document_id, len(chunks)):
                # Deleted or failed while we were working: don't leave vectors behind.
                self._remove_vectors(namespace, written, prefix)
                return
            logger.info(
                "Document %s ready scope=%s pages=%d chunks=%d in %d ms",
                document_id,
                document.scope,
                len(pages),
                len(chunks),
                (time.perf_counter() - start) * 1000,
            )
        except Exception as exc:
            self._handle_failure(document_id, namespace, written, prefix, exc)

    def list_documents(self, user: CurrentUser, scope: DocumentScope) -> list[Document]:
        if scope == "personal":
            return self.documents.list_personal(user.id)
        return self.documents.list_company()

    def get_document(self, user: CurrentUser, document_id: int) -> Document:
        document = self.documents.get(document_id)
        if document is None or (document.scope == "personal" and document.owner_user_id != user.id):
            raise NotFoundError("Document not found")
        return document

    def delete_document(self, user: CurrentUser, document_id: int) -> None:
        document = self.get_document(user, document_id)
        if document.scope == "company" and not user.is_admin:
            raise ForbiddenError("Only admins can manage company documents")
        # Owner oid only affects the filter, not the namespace or ids, so any user works here.
        namespace, _ = vector_location(document.scope, user.entra_oid)
        prefix = f"doc-{document.id}#"
        self._remove_vectors(
            namespace, [f"{prefix}{i}" for i in range(document.chunk_count)], prefix
        )
        self.storage.delete(document.storage_path)
        self.documents.delete(document)
        logger.info("Document %s deleted", document_id)

    def fail_interrupted(self) -> int:
        return self.documents.fail_all_processing(INTERRUPTED_MESSAGE)

    def _remove_vectors(self, namespace: str, ids: list[str], prefix: str) -> None:
        """Delete by exact ids, then by prefix as a backstop.

        Listing on eventually consistent stores can miss just-written vectors, so the
        exact ids are what guarantee cleanup.
        """
        self.vector_store.delete_ids(namespace, ids)
        self.vector_store.delete_by_prefix(namespace, prefix)

    def _handle_failure(
        self, document_id: int, namespace: str, written: list[str], prefix: str, exc: Exception
    ) -> None:
        if isinstance(exc, DocumentParseError):
            message = str(exc)
            logger.info("Document %s could not be parsed", document_id)
        elif isinstance(exc, VectorStoreUnavailableError):
            message = VECTOR_DOWN_MESSAGE
            logger.warning("Document %s failed: vector store unavailable", document_id)
        else:
            message = "Processing failed"
            logger.exception("Document %s failed unexpectedly", document_id)
        try:
            self._remove_vectors(namespace, written, prefix)
        except Exception:
            logger.warning("Could not remove partial vectors for document %s", document_id)
        try:
            self.documents.session.rollback()
            document = self.documents.get(document_id)
            if document is not None:
                self.documents.mark_failed(document, message)
        except Exception:
            logger.exception("Could not mark document %s as failed", document_id)


def _base_name(filename: str) -> str:
    """The file's own name, without any folder parts a browser or attacker sent."""
    name = PureWindowsPath(filename or "").name.strip()
    return name if name not in ("", ".", "..") else "document"


def _chunk_metadata(document: Document, owner_oid: str, index: int, page: int | None, text: str):
    metadata = {
        "document_id": document.id,
        "owner_oid": owner_oid,
        "filename": document.filename,
        "chunk_index": index,
        "text": text,
    }
    if page is not None:
        metadata["page"] = page
    return metadata
