import logging

from app.main import run_startup_tasks
from app.repositories.document_repo import DocumentRepository
from app.repositories.user_repo import UserRepository


def _processing_doc(session_factory):
    with session_factory() as session:
        user = UserRepository(session).upsert_from_identity("oid-a", "a@org", "A")
        return (
            DocumentRepository(session)
            .create(
                scope="personal",
                owner_user_id=user.id,
                filename="a.txt",
                content_type="text/plain",
                size_bytes=1,
                storage_path="x.txt",
            )
            .id
        )


def test_startup_marks_interrupted_documents_failed(session_factory, fake_vector_store):
    doc_id = _processing_doc(session_factory)
    run_startup_tasks(session_factory, fake_vector_store)
    with session_factory() as session:
        doc = DocumentRepository(session).get(doc_id)
        assert doc.status == "failed"
        assert doc.error_message == "Processing was interrupted; please upload again"


def test_startup_survives_vector_store_down(session_factory, fake_vector_store, caplog):
    fake_vector_store.available = False
    with caplog.at_level(logging.ERROR):
        run_startup_tasks(session_factory, fake_vector_store)  # must not raise
    assert "Vector store not ready" in caplog.text
