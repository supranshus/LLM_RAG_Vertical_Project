import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="genai-tests-")
os.environ.update(
    {
        "ENTRA_TENANT_ID": "tenant-123",
        "ENTRA_CLIENT_ID": "client-456",
        "LLM_API_KEY": "test",
        "PINECONE_API_KEY": "test",
        "LOG_DIR": os.path.join(_TMP, "logs"),
        "UPLOAD_DIR": os.path.join(_TMP, "uploads"),
        "DATABASE_URL": "sqlite:///" + os.path.join(_TMP, "unused.db").replace("\\", "/"),
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import app.db.models  # noqa: E402, F401  (registers models on Base.metadata)
from app.api.deps import (  # noqa: E402
    get_embeddings,
    get_file_storage,
    get_llm,
    get_session_factory,
    get_token_validator,
    get_vector_store,
)
from app.db.base import Base, make_engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.rag.storage import FileStorage  # noqa: E402
from tests.auth_helpers import make_token, test_validator  # noqa: E402
from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider, FakeVectorStore  # noqa: E402


@pytest.fixture
def engine(tmp_path):
    eng = make_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def db_session(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture
def fake_llm():
    return FakeLLMProvider()


@pytest.fixture
def fake_embeddings():
    return FakeEmbeddingProvider()


@pytest.fixture
def fake_vector_store():
    return FakeVectorStore()


@pytest.fixture
def app(session_factory, fake_llm, fake_embeddings, fake_vector_store, tmp_path):
    application = create_app(run_startup=False)
    overrides = application.dependency_overrides
    overrides[get_session_factory] = lambda: session_factory
    overrides[get_token_validator] = test_validator
    overrides[get_llm] = lambda: fake_llm
    overrides[get_embeddings] = lambda: fake_embeddings
    overrides[get_vector_store] = lambda: fake_vector_store
    overrides[get_file_storage] = lambda: FileStorage(str(tmp_path / "uploads"))
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def auth_header():
    def build(**claims) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(**claims)}"}

    return build


@pytest.fixture
def admin_header(auth_header):
    return auth_header(
        oid="oid-admin", name="Admin", preferred_username="admin@org", roles=["Admin"]
    )


@pytest.fixture
def bob_header(auth_header):
    return auth_header(oid="oid-bob", name="Bob", preferred_username="bob@org")
