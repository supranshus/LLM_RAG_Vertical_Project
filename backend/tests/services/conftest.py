import pytest

from app.core.security import CurrentUser
from app.rag.storage import FileStorage
from app.repositories.document_repo import DocumentRepository
from app.repositories.user_repo import UserRepository
from app.services.document_service import DocumentService
from app.services.retrieval_service import RetrievalService

MAX_UPLOAD_BYTES = 1024 * 1024


@pytest.fixture
def make_user(db_session):
    def build(oid: str, email: str, name: str, roles: tuple[str, ...] = ()) -> CurrentUser:
        user = UserRepository(db_session).upsert_from_identity(oid, email, name)
        return CurrentUser(user.id, oid, email, name, frozenset(roles))

    return build


@pytest.fixture
def alice(make_user):
    return make_user("oid-alice", "alice@org", "Alice")


@pytest.fixture
def bob(make_user):
    return make_user("oid-bob", "bob@org", "Bob")


@pytest.fixture
def admin(make_user):
    return make_user("oid-admin", "admin@org", "Admin", ("Admin",))


@pytest.fixture
def storage_root(tmp_path):
    return tmp_path / "uploads"


@pytest.fixture
def svc(db_session, storage_root, fake_embeddings, fake_vector_store):
    return DocumentService(
        DocumentRepository(db_session),
        FileStorage(str(storage_root)),
        fake_embeddings,
        fake_vector_store,
        chunk_size=1000,
        chunk_overlap=150,
        max_upload_bytes=MAX_UPLOAD_BYTES,
    )


@pytest.fixture
def retrieval(fake_embeddings, fake_vector_store):
    return RetrievalService(fake_embeddings, fake_vector_store, top_k=5, min_score=0.5)


@pytest.fixture
def index_text(svc):
    """Upload and process a .txt document, returning its id."""

    def run(user: CurrentUser, scope: str, filename: str, text: str) -> int:
        doc = svc.upload(user, scope, filename, "text/plain", text.encode())
        svc.process(doc.id)
        return doc.id

    return run
