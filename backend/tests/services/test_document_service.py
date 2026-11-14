from pathlib import Path

import pytest

from app.core.errors import (
    FileTooLargeError,
    ForbiddenError,
    NotFoundError,
    UnsupportedFileTypeError,
    VectorStoreUnavailableError,
)
from tests.docs_helpers import make_pdf
from tests.services.conftest import MAX_UPLOAD_BYTES


def test_upload_and_process_personal_txt(svc, alice, fake_vector_store, storage_root):
    doc = svc.upload(alice, "personal", "notes.txt", "text/plain", b"Sprint plan for Apollo")
    assert (doc.status, doc.scope, doc.filename, doc.size_bytes) == (
        "processing",
        "personal",
        "notes.txt",
        22,
    )
    assert (storage_root / doc.storage_path).read_bytes() == b"Sprint plan for Apollo"

    svc.process(doc.id)

    doc = svc.get_document(alice, doc.id)
    assert (doc.status, doc.chunk_count, doc.error_message) == ("ready", 1, None)
    assert fake_vector_store.ids("personal") == {f"doc-{doc.id}#0"}
    metadata = fake_vector_store.metadata("personal", f"doc-{doc.id}#0")
    assert metadata == {
        "document_id": doc.id,
        "owner_oid": "oid-alice",
        "filename": "notes.txt",
        "chunk_index": 0,
        "text": "Sprint plan for Apollo",
    }


def test_pdf_chunks_carry_page_numbers(svc, alice, fake_vector_store):
    doc = svc.upload(alice, "personal", "a.pdf", "application/pdf", make_pdf(["alpha", "beta"]))
    svc.process(doc.id)
    pages = sorted(
        fake_vector_store.metadata("personal", id_)["page"]
        for id_ in fake_vector_store.ids("personal")
    )
    assert pages == [1, 2]


def test_company_upload_goes_to_company_namespace(svc, admin, fake_vector_store):
    doc = svc.upload(admin, "company", "policy.md", "text/markdown", b"# Leave policy")
    svc.process(doc.id)
    assert fake_vector_store.ids("company") == {f"doc-{doc.id}#0"}
    assert fake_vector_store.ids("personal") == set()


def test_company_upload_requires_admin(svc, alice):
    with pytest.raises(ForbiddenError):
        svc.upload(alice, "company", "x.txt", "text/plain", b"x")


def test_unsupported_type_and_too_large(svc, alice):
    with pytest.raises(UnsupportedFileTypeError):
        svc.upload(alice, "personal", "x.exe", "application/octet-stream", b"MZ")
    with pytest.raises(UnsupportedFileTypeError):
        svc.upload(alice, "personal", "noextension", "text/plain", b"x")
    with pytest.raises(FileTooLargeError, match="1 MB"):
        svc.upload(alice, "personal", "big.txt", "text/plain", b"x" * (MAX_UPLOAD_BYTES + 1))
    assert svc.list_documents(alice, "personal") == []


def test_uppercase_extension_accepted(svc, alice):
    assert svc.upload(alice, "personal", "NOTES.TXT", "text/plain", b"x").filename == "NOTES.TXT"


def test_upload_filename_is_sanitised(svc, alice, storage_root):
    doc = svc.upload(alice, "personal", "..\\..\\evil.pdf", "application/pdf", make_pdf(["x"]))
    assert doc.filename == "evil.pdf"
    assert (storage_root / doc.storage_path).parent == storage_root
    assert ".." not in doc.storage_path
    assert svc.upload(alice, "personal", "a/b/../c.txt", "text/plain", b"x").filename == "c.txt"
    unicode_doc = svc.upload(alice, "personal", "प्रोजेक्ट.txt", "text/plain", b"x")
    assert unicode_doc.filename == "प्रोजेक्ट.txt"


def test_empty_text_marks_failed(svc, alice, fake_vector_store):
    doc = svc.upload(alice, "personal", "scan.pdf", "application/pdf", make_pdf([""]))
    svc.process(doc.id)
    doc = svc.get_document(alice, doc.id)
    assert doc.status == "failed"
    assert "scanned PDFs are not supported" in doc.error_message
    assert fake_vector_store.ids("personal") == set()


def test_corrupt_file_marks_failed(svc, alice):
    doc = svc.upload(alice, "personal", "bad.pdf", "application/pdf", b"not a pdf")
    svc.process(doc.id)
    doc = svc.get_document(alice, doc.id)
    assert (doc.status, doc.error_message) == ("failed", "Could not read this file")


def test_vector_store_down_marks_failed_no_vectors(svc, alice, fake_vector_store):
    doc = svc.upload(alice, "personal", "a.txt", "text/plain", b"hello world")
    fake_vector_store.available = False
    svc.process(doc.id)
    fake_vector_store.available = True
    doc = svc.get_document(alice, doc.id)
    assert doc.status == "failed"
    assert doc.error_message == "Document search service is unavailable; please try again later"
    assert fake_vector_store.ids("personal") == set()


def test_unexpected_error_marks_failed(svc, alice, fake_embeddings):
    doc = svc.upload(alice, "personal", "a.txt", "text/plain", b"hello world")
    fake_embeddings.embed_documents = lambda texts: (_ for _ in ()).throw(RuntimeError("bug"))
    svc.process(doc.id)
    doc = svc.get_document(alice, doc.id)
    assert (doc.status, doc.error_message) == ("failed", "Processing failed")


def test_process_after_delete_leaves_no_vectors(svc, alice, fake_vector_store):
    doc = svc.upload(alice, "personal", "a.txt", "text/plain", b"hello world")
    svc.delete_document(alice, doc.id)
    svc.process(doc.id)  # must not raise
    assert fake_vector_store.ids("personal") == set()


def test_delete_during_processing_cleans_up_vectors(svc, alice, fake_vector_store):
    doc = svc.upload(alice, "personal", "a.txt", "text/plain", b"hello world")
    original_upsert = fake_vector_store.upsert

    def upsert_then_user_deletes(namespace, records):
        original_upsert(namespace, records)
        svc.documents.delete(svc.documents.get(doc.id))

    fake_vector_store.upsert = upsert_then_user_deletes
    svc.process(doc.id)
    assert fake_vector_store.ids("personal") == set()


def test_delete_removes_vectors_file_and_row(svc, alice, fake_vector_store, storage_root):
    doc = svc.upload(alice, "personal", "a.txt", "text/plain", b"hello world")
    svc.process(doc.id)
    stored = storage_root / doc.storage_path
    svc.delete_document(alice, doc.id)
    assert fake_vector_store.ids("personal") == set()
    assert not stored.exists()
    with pytest.raises(NotFoundError):
        svc.get_document(alice, doc.id)


def test_delete_keeps_row_when_vector_store_down(svc, alice, fake_vector_store):
    doc = svc.upload(alice, "personal", "a.txt", "text/plain", b"hello world")
    svc.process(doc.id)
    fake_vector_store.available = False
    with pytest.raises(VectorStoreUnavailableError):
        svc.delete_document(alice, doc.id)
    assert svc.get_document(alice, doc.id).id == doc.id


def test_other_users_personal_doc_is_not_found(svc, alice, bob):
    doc = svc.upload(alice, "personal", "a.txt", "text/plain", b"secret")
    with pytest.raises(NotFoundError):
        svc.get_document(bob, doc.id)
    with pytest.raises(NotFoundError):
        svc.delete_document(bob, doc.id)
    assert svc.list_documents(bob, "personal") == []
    assert [d.id for d in svc.list_documents(alice, "personal")] == [doc.id]


def test_company_docs_visible_to_all_but_delete_requires_admin(svc, admin, alice):
    doc = svc.upload(admin, "company", "c.txt", "text/plain", b"handbook")
    assert [d.id for d in svc.list_documents(alice, "company")] == [doc.id]
    assert svc.get_document(alice, doc.id).id == doc.id
    with pytest.raises(ForbiddenError):
        svc.delete_document(alice, doc.id)
    svc.delete_document(admin, doc.id)
    assert svc.list_documents(alice, "company") == []


def test_fail_interrupted(svc, alice):
    svc.upload(alice, "personal", "a.txt", "text/plain", b"x")
    svc.upload(alice, "personal", "b.txt", "text/plain", b"y")
    assert svc.fail_interrupted() == 2
    statuses = {d.status for d in svc.list_documents(alice, "personal")}
    assert statuses == {"failed"}


def test_get_missing_document_not_found(svc, alice):
    with pytest.raises(NotFoundError):
        svc.get_document(alice, 12345)


def test_stored_path_is_inside_root(svc, alice, storage_root):
    doc = svc.upload(alice, "personal", "a.md", "text/markdown", b"x")
    assert Path(storage_root, doc.storage_path).resolve().parent == storage_root.resolve()


def test_process_takes_owner_from_the_document(svc, alice, fake_vector_store):
    doc = svc.upload(alice, "personal", "a.txt", "text/plain", b"hello world")
    svc.process(doc.id)
    assert fake_vector_store.metadata("personal", f"doc-{doc.id}#0")["owner_oid"] == "oid-alice"


def test_process_does_not_revive_failed_document(svc, alice, fake_vector_store):
    doc = svc.upload(alice, "personal", "a.txt", "text/plain", b"hello world")
    svc.fail_interrupted()
    svc.process(doc.id)
    assert svc.get_document(alice, doc.id).status == "failed"
    assert fake_vector_store.ids("personal") == set()


def test_delete_removes_vectors_even_when_listing_lags(svc, alice, fake_vector_store):
    doc = svc.upload(alice, "personal", "a.txt", "text/plain", b"x " * 900)
    svc.process(doc.id)
    assert svc.get_document(alice, doc.id).chunk_count == 2
    fake_vector_store.lag_listing = True
    svc.delete_document(alice, doc.id)
    assert fake_vector_store.ids("personal") == set()


def test_delete_during_processing_cleans_up_when_listing_lags(svc, alice, fake_vector_store):
    doc = svc.upload(alice, "personal", "a.txt", "text/plain", b"hello world")
    fake_vector_store.lag_listing = True
    original_upsert = fake_vector_store.upsert

    def upsert_then_user_deletes(namespace, records):
        original_upsert(namespace, records)
        svc.delete_document(alice, doc.id)

    fake_vector_store.upsert = upsert_then_user_deletes
    svc.process(doc.id)
    assert fake_vector_store.ids("personal") == set()
