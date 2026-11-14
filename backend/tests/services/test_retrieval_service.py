from app.services.retrieval_service import RetrievedChunk, vector_location


def test_vector_location():
    assert vector_location("personal", "oid-a") == ("personal", {"owner_oid": {"$eq": "oid-a"}})
    assert vector_location("company", "oid-a") == ("company", None)


def test_personal_search_never_returns_other_users_chunks(
    retrieval, alice, bob, index_text, fake_vector_store
):
    index_text(alice, "personal", "alice.txt", "apollo sprint plan")
    bob_doc = index_text(bob, "personal", "bob.txt", "apollo sprint plan")

    results = retrieval.search(bob, "personal", "apollo sprint plan")

    assert {c.document_id for c in results} == {bob_doc}
    assert fake_vector_store.queries[-1] == ("personal", {"owner_oid": {"$eq": "oid-bob"}})


def test_search_returns_chunk_details(retrieval, alice, index_text):
    doc_id = index_text(alice, "personal", "alice.txt", "apollo sprint plan")
    [chunk] = retrieval.search(alice, "personal", "apollo sprint plan")
    assert isinstance(chunk, RetrievedChunk)
    assert (chunk.document_id, chunk.filename, chunk.page, chunk.text) == (
        doc_id,
        "alice.txt",
        None,
        "apollo sprint plan",
    )
    assert chunk.score > 0.99


def test_company_search_has_no_filter(retrieval, admin, alice, index_text, fake_vector_store):
    doc_id = index_text(admin, "company", "handbook.txt", "leave policy days")
    results = retrieval.search(alice, "company", "leave policy")
    assert [c.document_id for c in results] == [doc_id]
    assert fake_vector_store.queries[-1] == ("company", None)


def test_low_scores_dropped(retrieval, alice, index_text):
    index_text(alice, "personal", "alice.txt", "apollo sprint plan")
    assert retrieval.search(alice, "personal", "holiday photos beach") == []


def test_top_k_override(retrieval, admin, index_text):
    for i in range(3):
        index_text(admin, "company", f"d{i}.txt", "same words here")
    assert len(retrieval.search(admin, "company", "same words here", top_k=2)) == 2


def test_float_metadata_ids_are_cast_to_int(retrieval, alice, fake_vector_store, fake_embeddings):
    from app.rag.vectorstore.base import VectorRecord

    fake_vector_store.upsert(
        "personal",
        [
            VectorRecord(
                "doc-7#0",
                fake_embeddings.embed_query("hello"),
                {
                    "document_id": 7.0,
                    "owner_oid": "oid-alice",
                    "filename": "f.pdf",
                    "page": 3.0,
                    "chunk_index": 0.0,
                    "text": "hello",
                },
            )
        ],
    )
    [chunk] = retrieval.search(alice, "personal", "hello")
    assert (chunk.document_id, chunk.page) == (7, 3)
    assert isinstance(chunk.document_id, int) and isinstance(chunk.page, int)
