from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import Document, User
from app.db.models._common import utcnow


class DocumentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        scope: str,
        owner_user_id: int,
        filename: str,
        content_type: str,
        size_bytes: int,
        storage_path: str,
    ) -> Document:
        document = Document(
            scope=scope,
            owner_user_id=owner_user_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
        )
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document

    def get(self, document_id: int) -> Document | None:
        return self.session.get(Document, document_id)

    def get_owner_oid(self, document: Document) -> str:
        return self.session.scalar(select(User.entra_oid).where(User.id == document.owner_user_id))

    def mark_ready_if_processing(self, document_id: int, chunk_count: int) -> bool:
        """Mark ready only if the row still exists and is still processing.

        Works against the database directly, so a delete or failure recorded by another
        session meanwhile is respected. Returns False when nothing was updated.
        """
        result = self.session.execute(
            update(Document)
            .where(Document.id == document_id, Document.status == "processing")
            .values(
                status="ready", chunk_count=chunk_count, error_message=None, updated_at=utcnow()
            )
        )
        self.session.commit()
        return result.rowcount == 1

    def list_personal(self, owner_user_id: int) -> list[Document]:
        return list(
            self.session.scalars(
                select(Document)
                .where(Document.scope == "personal", Document.owner_user_id == owner_user_id)
                .order_by(Document.created_at.desc(), Document.id.desc())
            )
        )

    def list_company(self) -> list[Document]:
        return list(
            self.session.scalars(
                select(Document)
                .where(Document.scope == "company")
                .order_by(Document.created_at.desc(), Document.id.desc())
            )
        )

    def mark_ready(self, document: Document, chunk_count: int) -> Document:
        document.status = "ready"
        document.chunk_count = chunk_count
        document.error_message = None
        return self._touch(document)

    def mark_failed(self, document: Document, message: str) -> Document:
        document.status = "failed"
        document.error_message = message
        return self._touch(document)

    def fail_all_processing(self, message: str) -> int:
        result = self.session.execute(
            update(Document)
            .where(Document.status == "processing")
            .values(status="failed", error_message=message, updated_at=utcnow())
        )
        self.session.commit()
        return result.rowcount

    def delete(self, document: Document) -> None:
        self.session.delete(document)
        self.session.commit()

    def _touch(self, document: Document) -> Document:
        document.updated_at = utcnow()
        self.session.commit()
        self.session.refresh(document)
        return document
