from app.repositories.document_repo import DocumentRepository
from app.repositories.user_repo import UserRepository


def _create(repo, user_id, scope, name):
    return repo.create(
        scope=scope,
        owner_user_id=user_id,
        filename=name,
        content_type="text/plain",
        size_bytes=5,
        storage_path=f"{name}.bin",
    )


def test_document_lists_split_by_scope_and_owner(db_session):
    users = UserRepository(db_session)
    a = users.upsert_from_identity("oid-a", "a@org", "A")
    b = users.upsert_from_identity("oid-b", "b@org", "B")
    repo = DocumentRepository(db_session)
    mine = _create(repo, a.id, "personal", "a.txt")
    _create(repo, b.id, "personal", "b.txt")
    company = _create(repo, a.id, "company", "c.txt")

    assert mine.status == "processing" and mine.chunk_count == 0
    assert [d.id for d in repo.list_personal(a.id)] == [mine.id]
    assert [d.id for d in repo.list_company()] == [company.id]
    assert repo.get(mine.id).filename == "a.txt"
    assert repo.get(9999) is None


def test_mark_ready_failed_and_fail_all_processing(db_session):
    a = UserRepository(db_session).upsert_from_identity("oid-a", "a@org", "A")
    repo = DocumentRepository(db_session)
    ready = repo.mark_ready(_create(repo, a.id, "personal", "r.txt"), 3)
    assert (ready.status, ready.chunk_count) == ("ready", 3)
    failed = repo.mark_failed(_create(repo, a.id, "personal", "f.txt"), "bad")
    assert (failed.status, failed.error_message) == ("failed", "bad")

    p1 = _create(repo, a.id, "personal", "p1.txt")
    p2 = _create(repo, a.id, "company", "p2.txt")
    assert repo.fail_all_processing("x") == 2
    db_session.expire_all()
    for doc in (repo.get(p1.id), repo.get(p2.id)):
        assert (doc.status, doc.error_message) == ("failed", "x")
    assert repo.get(ready.id).status == "ready"


def test_delete(db_session):
    a = UserRepository(db_session).upsert_from_identity("oid-a", "a@org", "A")
    repo = DocumentRepository(db_session)
    doc = _create(repo, a.id, "personal", "d.txt")
    repo.delete(doc)
    assert repo.get(doc.id) is None


def test_ids_are_not_reused_after_delete(db_session):
    a = UserRepository(db_session).upsert_from_identity("oid-a", "a@org", "A")
    repo = DocumentRepository(db_session)
    _create(repo, a.id, "personal", "one.txt")
    latest = _create(repo, a.id, "personal", "two.txt")
    repo.delete(latest)
    assert _create(repo, a.id, "personal", "three.txt").id > latest.id


def test_mark_ready_if_processing(db_session):
    a = UserRepository(db_session).upsert_from_identity("oid-a", "a@org", "A")
    repo = DocumentRepository(db_session)
    doc = _create(repo, a.id, "personal", "a.txt")
    assert repo.get_owner_oid(doc) == "oid-a"
    assert repo.mark_ready_if_processing(doc.id, 4) is True
    db_session.expire_all()
    assert (repo.get(doc.id).status, repo.get(doc.id).chunk_count) == ("ready", 4)
    assert repo.mark_ready_if_processing(doc.id, 5) is False
    assert repo.mark_ready_if_processing(9999, 1) is False
