# GenAI Boilerplate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A copyable starter repo: Streamlit frontend + FastAPI backend (api → service → repo), SQLite, swappable LLM layer (Groq default), document Q&A on Pinecone (swappable), Microsoft Entra ID single-tenant sign-in with an Admin app role, text file logging, Docker.

**Architecture:** Two independent Python apps in one repo (`backend/`, `frontend/`), each with its own `pyproject.toml`. Streamlit signs the user in with MSAL (auth-code flow) and calls the API with the user's access token; the API validates every token itself and reads roles from it. Backend is sync FastAPI + sync SQLAlchemy 2.x on SQLite with Alembic. LLM, embeddings and vector store each sit behind a small interface chosen by config; tests use in-memory fakes for all three.

**Tech Stack:** Python 3.12, uv, FastAPI, uvicorn, SQLAlchemy 2.x, Alembic, pydantic-settings, PyJWT[crypto], groq SDK, pinecone SDK, pypdf, python-docx, httpx, Streamlit, MSAL for Python, pytest, Ruff, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-24-genai-boilerplate-design.md`

## Global Constraints

- Python 3.12. `uv` manages deps; `backend/pyproject.toml` and `frontend/pyproject.toml` (one per app); shared `ruff.toml` at repo root (line-length 100, target py312).
- Add deps with `uv add` (current stable); floors: fastapi>=0.115, sqlalchemy>=2.0, alembic>=1.13, pydantic-settings>=2.4, pyjwt[crypto]>=2.9, groq>=0.11, pinecone>=7.0, pypdf>=5.0, python-docx>=1.1, python-multipart>=0.0.9, streamlit>=1.40, msal>=1.31, httpx>=0.27. Commit `uv.lock`.
- Layering: **api** calls services only (no SQLAlchemy, LLM, Pinecone imports); **service** holds logic, calls repos and the `LLMProvider` / `EmbeddingProvider` / `VectorStore` interfaces, raises `AppError` subclasses, never `HTTPException`; **repo** does all DB access, no business rules, no HTTP. Wiring lives in `app/api/deps.py` via `Depends`.
- Sync throughout (sync SQLAlchemy, sync route functions, sync provider SDK clients).
- Repos commit their own writes (`add` → `commit` → `refresh`).
- Error body everywhere: `{"error": {"code": "...", "message": "...", "request_id": "..."}}`.
- Log line format: `%(asctime)s | %(levelname)s | %(name)s | req=%(request_id)s user=%(user)s | %(message)s`, datefmt `%Y-%m-%d %H:%M:%S`. Console + `TimedRotatingFileHandler(when="midnight", backupCount=LOG_RETENTION_DAYS, encoding="utf-8")`. Files `<LOG_DIR>/backend.log`, `<LOG_DIR>/frontend.log`.
- Never log tokens, secrets, `Authorization` headers, prompt/response text, or document text. LLM/embedding/vector calls log provider, model, counts, latency, success/failure only.
- Auth: single tenant; v2 tokens (`iss = https://login.microsoftonline.com/{tenant}/v2.0`); `aud` ∈ {`<client_id>`, `api://<client_id>`}; `tid` = tenant; `acct` = 1 → 403; missing `acct` → 403 + log naming the missing optional claim. Roles only from token `roles` (`"Admin"`).
- Documents: namespaces `personal` and `company` only. Every personal vector has `owner_oid` metadata; every personal query has filter `{"owner_oid": {"$eq": <caller oid>}}`, set server-side. Vector ids `doc-<document_id>#<chunk_index>`.
- Pinecone must not be needed to start the API or for sign-in/plain chat; vector failures → 502 `vector_store_unavailable`.
- Config from environment / `.env` (`env_file=("../.env", ".env")`, `extra="ignore"`); missing required values fail at startup.
- Apps write only under `data/` (SQLite, `data/uploads/`) and `logs/`; directories are created if missing.
- Local (non-Docker) run must work on Windows.
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Review Focus

1. **LLM rate limit / outage** (Groq free tier) → 429/502/504 JSON, friendly UI message, **no orphan user message** saved. Tests: Task 9 `test_send_message_rate_limited_persists_nothing`, `test_stream_rate_limited_before_first_chunk_returns_429`.
2. **Stream dies mid-reply** → partial text + `[Response interrupted. Please try again.]`, assistant message not saved. Test: Task 9 `test_stream_interrupted_mid_reply`.
3. **Upload filename with path parts or non-ASCII** (`..\..\evil.pdf`, `प्रोजेक्ट.txt`) → file stored under a generated name inside `UPLOAD_DIR`; listing shows only the base name, unicode intact. Test: Task 8 `test_upload_filename_is_sanitised`.
4. **Document deleted while still processing** → no orphan vectors left, background job exits quietly. Test: Task 8 `test_process_after_delete_leaves_no_vectors`.
5. **First run on a fresh clone** (no `data/`, `logs/`, `data/uploads/`) → directories created, no crash. Tests: Task 1 `test_setup_logging_creates_dir_and_writes_utf8`, Task 2 `test_make_engine_creates_sqlite_parent_dir`, Task 6 `test_storage_creates_root_and_round_trips`.

---

### Task 1: Repo scaffold, backend settings, logging

**Files:**
- Create: `.gitignore`, `ruff.toml`, `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/core/__init__.py`, `backend/app/core/config.py`, `backend/app/core/logging.py`, `backend/app/core/types.py`
- Test: `backend/tests/__init__.py`, `backend/tests/core/test_config.py`, `backend/tests/core/test_logging.py`

**Interfaces:**
- Produces:
  - `app.core.config.Settings`: `entra_tenant_id: str`, `entra_client_id: str`, `database_url: str = "sqlite:///./data/app.db"`, `llm_provider: str = "groq"`, `llm_model: str = "llama-3.3-70b-versatile"`, `llm_api_key: SecretStr`, `llm_temperature: float = 0.7`, `llm_max_tokens: int = 1024`, `llm_timeout_seconds: float = 60.0`, `chat_system_prompt: str = "You are a helpful assistant."`, `chat_history_limit: int = 20`, `vector_store_provider: str = "pinecone"`, `embedding_provider: str = "pinecone"`, `pinecone_api_key: SecretStr`, `pinecone_index_name: str = "genai-boilerplate"`, `pinecone_cloud: str = "aws"`, `pinecone_region: str = "us-east-1"`, `embedding_model: str = "multilingual-e5-large"`, `embedding_dimension: int = 1024`, `rag_top_k: int = 5`, `rag_min_score: float = 0.78`, `rag_chunk_size: int = 1000`, `rag_chunk_overlap: int = 150`, `max_upload_mb: int = 10`, `upload_dir: str = "./data/uploads"`, `log_level: str = "INFO"`, `log_dir: str = "./logs"`, `log_retention_days: int = 14`.
  - `get_settings() -> Settings` (`lru_cache`).
  - `app.core.types`: `DocumentScope = Literal["personal", "company"]`, `KnowledgeScope = Literal["none", "personal", "company"]`, `DocumentStatus = Literal["processing", "ready", "failed"]`.
  - `app.core.logging`: `request_id_var: ContextVar[str]` (default `"-"`), `user_var: ContextVar[str]` (default `"-"`), `ContextFilter(logging.Filter)`, `setup_logging(log_dir: str, level: str, filename: str) -> None` (idempotent; filter attached to handlers so third-party records get the fields).

- [ ] **Step 1: Init** — `git init` at repo root. `.gitignore`: `.venv/`, `__pycache__/`, `.env`, `data/`, `logs/`, `.pytest_cache/`, `.ruff_cache/`. In `backend/`: `uv init --app --python 3.12 --no-readme`, delete generated script, `uv add fastapi "uvicorn[standard]" sqlalchemy alembic pydantic-settings "pyjwt[crypto]" groq pinecone pypdf python-docx python-multipart httpx`, `uv add --dev pytest ruff cryptography reportlab`. `[tool.pytest.ini_options] testpaths = ["tests"]`, `pythonpath = ["."]`.

- [ ] **Step 2: Write failing tests**

```python
REQUIRED = ("ENTRA_TENANT_ID", "ENTRA_CLIENT_ID", "LLM_API_KEY", "PINECONE_API_KEY")

def test_settings_require_secrets(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for k in REQUIRED: monkeypatch.delenv(k, raising=False)
    with pytest.raises(ValidationError): Settings()

def test_settings_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for k in REQUIRED: monkeypatch.setenv(k, "x")
    s = Settings()
    assert (s.llm_provider, s.vector_store_provider, s.embedding_model) == ("groq", "pinecone", "multilingual-e5-large")
    assert (s.rag_top_k, s.rag_min_score, s.rag_chunk_size, s.rag_chunk_overlap) == (5, 0.78, 1000, 150)
    assert (s.max_upload_mb, s.chat_history_limit, s.log_retention_days) == (10, 20, 14)

def test_setup_logging_creates_dir_and_writes_utf8(tmp_path):
    log_dir = tmp_path / "nested" / "logs"
    setup_logging(str(log_dir), "INFO", "backend.log")
    request_id_var.set("ab12"); user_var.set("aditi@org")
    logging.getLogger("app.test").info("namaste नमस्ते")
    for h in logging.getLogger().handlers: h.flush()
    line = (log_dir / "backend.log").read_text(encoding="utf-8").splitlines()[-1]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| INFO \| app\.test \| req=ab12 user=aditi@org \| namaste नमस्ते", line)

def test_defaults_when_no_context(tmp_path):
    setup_logging(str(tmp_path), "INFO", "backend.log")
    contextvars.Context().run(logging.getLogger("x").info, "hi")
    # flush, then: last line contains "req=- user=- | hi"
```

- [ ] **Step 3: Run — expect FAIL.** `cd backend && uv run pytest tests/core -v`
- [ ] **Step 4: Implement** `config.py`, `types.py`, `logging.py`.
- [ ] **Step 5: Run — expect PASS;** `uv run ruff check . && uv run ruff format --check .`
- [ ] **Step 6: Commit** (include `docs/`) — `chore: scaffold backend with settings and text logging`

---

### Task 2: Errors, DB engine, app factory, request middleware, health

**Files:**
- Create: `backend/app/core/errors.py`, `backend/app/db/__init__.py`, `backend/app/db/base.py`, `backend/app/main.py`, `backend/app/api/__init__.py`, `backend/app/api/deps.py`, `backend/app/api/v1/__init__.py`, `backend/app/api/v1/routes/__init__.py`, `backend/app/api/v1/routes/health.py`
- Test: `backend/tests/conftest.py`, `backend/tests/test_app.py`, `backend/tests/db/test_base.py`

**Interfaces:**
- Consumes: `get_settings`, `setup_logging`, `request_id_var`.
- Produces:
  - `app.core.errors.AppError(Exception)`: class attrs `code = "internal_error"`, `status_code = 500`; `__init__(self, message: str)`. Subclasses (status, code): `UnauthorizedError` (401 `unauthorized`), `ForbiddenError` (403 `forbidden`), `NotFoundError` (404 `not_found`), `FileTooLargeError` (413 `file_too_large`), `UnsupportedFileTypeError` (415 `unsupported_file_type`), `LLMRateLimitError` (429 `llm_rate_limited`), `LLMUnavailableError` (502 `llm_unavailable`), `VectorStoreUnavailableError` (502 `vector_store_unavailable`), `LLMTimeoutError` (504 `llm_timeout`).
  - `register_exception_handlers(app) -> None`: `AppError` → its status/code; `RequestValidationError` → 422 `validation_error` (message summarises fields); any other `Exception` → 500 `internal_error`, message `"Internal server error"`, traceback logged.
  - `app.db.base`: `Base(DeclarativeBase)`; `make_engine(database_url: str) -> Engine` (sqlite: create parent dir, `check_same_thread=False`, `PRAGMA foreign_keys=ON` on connect); `get_sessionmaker() -> sessionmaker[Session]` (`lru_cache`, from settings, `expire_on_commit=False`).
  - `app.api.deps`: `get_session_factory() -> sessionmaker[Session]` (returns `get_sessionmaker()`); `get_db(factory=Depends(get_session_factory)) -> Iterator[Session]`.
  - `app.main`: `create_app(run_startup: bool = True) -> FastAPI` (logging setup, handlers, middleware, routers; startup work added in Task 8 runs only when `run_startup`); module-level `app = create_app()`.
  - Middleware: `X-Request-ID` from request or `uuid4().hex[:12]`, sets `request_id_var`, logs `"%s %s -> %s (%.0f ms)"`, sets response header.
  - `GET /health` (no auth) → 200 `{"status": "ok", "database": "ok"}`; DB `SELECT 1` fails → 503 `{"status": "degraded", "database": "error"}`. (Task 8 adds `vector_store`.)
  - `tests/conftest.py`: sets env at import — `ENTRA_TENANT_ID=tenant-123`, `ENTRA_CLIENT_ID=client-456`, `LLM_API_KEY=test`, `PINECONE_API_KEY=test`, `LOG_DIR`/`UPLOAD_DIR` under a session temp dir. Fixtures: `engine` (temp-file SQLite, `create_all`), `session_factory`, `db_session`, `client` = `TestClient(create_app(run_startup=False))` with `get_session_factory` overridden; `app` fixture exposes the app so later tasks add overrides.

- [ ] **Step 1: Write failing tests**

```python
def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok", "database": "ok"}

def test_request_id_echoed_and_generated(client):
    assert client.get("/health", headers={"X-Request-ID": "abc"}).headers["X-Request-ID"] == "abc"
    assert len(client.get("/health").headers["X-Request-ID"]) == 12

def test_app_error_shape(client_with_route):  # test-only GET /boom raises NotFoundError("nope")
    r = client_with_route.get("/boom", headers={"X-Request-ID": "r1"})
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "not_found", "message": "nope", "request_id": "r1"}}

def test_unhandled_error_is_500_json(client_with_route):  # GET /crash raises RuntimeError("secret")
    r = client_with_route.get("/crash")
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal_error" and "secret" not in r.text

def test_make_engine_creates_sqlite_parent_dir(tmp_path):
    eng = make_engine(f"sqlite:///{tmp_path / 'a' / 'b' / 'app.db'}")
    with eng.connect() as c: assert c.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    assert (tmp_path / "a" / "b").is_dir()
```

(`client_with_route` uses `raise_server_exceptions=False`.)

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run — expect PASS; ruff clean.**
- [ ] **Step 5: Commit** — `feat(backend): app factory, error handling, request logging, health`

---

### Task 3: Models, Alembic, repositories

**Files:**
- Create: `backend/app/db/models/__init__.py`, `user.py`, `conversation.py`, `message.py`, `document.py`; `backend/app/repositories/__init__.py`, `user_repo.py`, `conversation_repo.py`, `message_repo.py`, `document_repo.py`; `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/alembic/versions/0001_initial.py`
- Test: `backend/tests/repositories/test_user_repo.py`, `test_conversation_repo.py`, `test_message_repo.py`, `test_document_repo.py`, `backend/tests/db/test_migrations.py`

**Interfaces:**
- Consumes: `Base`, `make_engine`, `get_settings`, `app.core.types`.
- Produces:
  - Models per spec §5.5: `User(id, entra_oid unique, email, display_name, created_at, last_seen_at)`; `Conversation(id, user_id FK CASCADE, title, knowledge_scope str default "none", created_at, updated_at)`; `Message(id, conversation_id FK CASCADE, role, content Text, model?, prompt_tokens?, completion_tokens?, sources JSON?, created_at)`; `Document(id, scope, owner_user_id FK users, filename, content_type, size_bytes, storage_path, status default "processing", error_message?, chunk_count default 0, created_at, updated_at)`. Timestamps `datetime.now(timezone.utc)`.
  - `UserRepository(session)`: `get_by_oid(oid) -> User | None`; `upsert_from_identity(oid, email, display_name) -> User` (sets `last_seen_at`); `list_with_stats() -> list[UserStats]` (last_seen desc). `@dataclass UserStats: user: User; conversation_count: int; message_count: int`.
  - `ConversationRepository(session)`: `create(user_id: int, title: str, knowledge_scope: str = "none") -> Conversation`; `get_for_user(conversation_id, user_id) -> Conversation | None`; `list_for_user(user_id) -> list[Conversation]` (updated_at desc); `update(conversation, *, title: str | None = None) -> Conversation` (bumps `updated_at`).
  - `MessageRepository(session)`: `add(conversation_id, role, content, *, model=None, prompt_tokens=None, completion_tokens=None, sources: list[dict] | None = None) -> Message`; `list_for_conversation(conversation_id, limit: int | None = None) -> list[Message]` (chronological; last `limit`).
  - `DocumentRepository(session)`: `create(*, scope, owner_user_id, filename, content_type, size_bytes, storage_path) -> Document`; `get(document_id) -> Document | None`; `list_personal(owner_user_id) -> list[Document]`; `list_company() -> list[Document]` (both created desc); `mark_ready(document, chunk_count: int) -> Document`; `mark_failed(document, message: str) -> Document`; `fail_all_processing(message: str) -> int`; `delete(document) -> None`.
  - `alembic/env.py`: URL from `get_settings().database_url`, `target_metadata = Base.metadata`, `render_as_batch=True`.

- [ ] **Step 1: Write failing tests**

```python
def test_upsert_creates_then_updates(db_session):
    repo = UserRepository(db_session)
    u1 = repo.upsert_from_identity("oid-1", "a@org", "A"); u2 = repo.upsert_from_identity("oid-1", "a2@org", "A Two")
    assert u1.id == u2.id and u2.email == "a2@org"

def test_list_with_stats_counts(db_session):  # A: 2 conversations / 3 messages; B: none
    stats = {s.user.entra_oid: s for s in UserRepository(db_session).list_with_stats()}
    assert (stats["oid-a"].conversation_count, stats["oid-a"].message_count) == (2, 3)
    assert (stats["oid-b"].conversation_count, stats["oid-b"].message_count) == (0, 0)

def test_get_for_user_hides_other_users_conversation(db_session): ...  # B → None, A → found
def test_conversation_knowledge_scope_persisted(db_session): ...      # create(..., "company") round-trips
def test_list_for_conversation_limit_returns_last_n_chronological(db_session): ...  # m1..m5, limit=2 → [m4, m5]
def test_message_sources_round_trip(db_session): ...  # [{"document_id": 1, "filename": "a.pdf", "page": 2}]
def test_deleting_conversation_cascades_messages(db_session): ...
def test_document_lists_split_by_scope_and_owner(db_session): ...  # personal(A), personal(B), company(A) → list_personal(A) has 1, list_company has 1
def test_mark_ready_failed_and_fail_all_processing(db_session):
    # two processing docs → fail_all_processing("x") == 2; both status "failed", error_message "x"

def test_alembic_upgrade_head_matches_models(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path/'m.db'}"; monkeypatch.setenv("DATABASE_URL", url); get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")
    eng = make_engine(url)
    assert {"users", "conversations", "messages", "documents"} <= set(inspect(eng).get_table_names())
    with eng.connect() as c: assert compare_metadata(MigrationContext.configure(c), Base.metadata) == []
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement models + repos; `uv run alembic revision --autogenerate -m initial`, rename to `0001_initial.py`, review by hand.**
- [ ] **Step 4: Run — expect PASS; ruff clean.**
- [ ] **Step 5: Commit** — `feat(backend): models, initial migration, repositories`

---

### Task 4: Entra token validation, current user, `/me`

**Files:**
- Create: `backend/app/core/security.py`, `backend/app/services/__init__.py`, `backend/app/services/user_service.py`, `backend/app/api/schemas/__init__.py`, `backend/app/api/schemas/user.py`, `backend/app/api/v1/routes/me.py`
- Modify: `backend/app/api/deps.py`, `backend/app/main.py`
- Test: `backend/tests/auth_helpers.py`, `backend/tests/core/test_security.py`, `backend/tests/api/test_me.py`; extend `conftest.py`

**Interfaces:**
- Consumes: `UserRepository`, errors, `get_settings`, `user_var`.
- Produces:
  - `security.TokenClaims` (frozen dataclass): `oid`, `tid`, `name`, `preferred_username`, `roles: frozenset[str]`.
  - `security.TokenValidator(tenant_id: str, client_id: str, key_resolver: Callable[[str], Any] | None = None)`; `validate(token: str) -> TokenClaims`. Default resolver `PyJWKClient(f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys", cache_keys=True).get_signing_key_from_jwt(token).key`. `jwt.decode(algorithms=["RS256"], audience=[client_id, f"api://{client_id}"], issuer=f"https://login.microsoftonline.com/{tenant_id}/v2.0", leeway=60, options={"require": ["exp", "iat", "oid", "tid"]})`. Any JWT/key error or `tid` mismatch → `UnauthorizedError("Invalid or expired token")`. Missing `acct` → log ERROR `"Token has no 'acct' claim; add the acct optional claim to the access token in the app registration"` + `ForbiddenError("Account type could not be verified")`. `acct == 1` → `ForbiddenError("Guest accounts are not allowed")`.
  - `security.CurrentUser` (frozen dataclass): `id: int`, `entra_oid: str`, `email: str`, `display_name: str`, `roles: frozenset[str]`; `is_admin` property. `ADMIN_ROLE = "Admin"`.
  - `UserService(users: UserRepository)`: `sync_user(claims: TokenClaims) -> CurrentUser` (upsert every request; email = `preferred_username`).
  - `deps`: `get_token_validator()` (lru_cache), `get_user_service(db)`, `get_current_user(credentials=Depends(HTTPBearer(auto_error=False)), validator=..., users=...) -> CurrentUser` (no header → `UnauthorizedError("Missing bearer token")`; sets `user_var`), `require_admin(user) -> CurrentUser` (`ForbiddenError("Admin role required")`).
  - `GET /api/v1/me` → `MeRead{id, email, display_name, roles: list[str] (sorted), is_admin}`.
  - `tests/auth_helpers.py`: `TEST_KEY` (RSA, generated once); `make_token(**overrides) -> str` with defaults `iss` (v2, tenant-123), `aud="client-456"`, `tid="tenant-123"`, `oid="oid-alice"`, `name="Alice"`, `preferred_username="alice@org"`, `acct=0`, `iat`, `exp=now+3600` (override value `None` deletes the claim); `test_validator()` using `TEST_KEY.public_key()`.
  - Conftest: `client` overrides `get_token_validator`; fixtures `auth_header(**claims) -> dict` (factory), `admin_header` (`oid="oid-admin"`, `name="Admin"`, `preferred_username="admin@org"`, `roles=["Admin"]`), `bob_header` (`oid="oid-bob"`, `name="Bob"`, `preferred_username="bob@org"`).

- [ ] **Step 1: Write failing tests**

```python
V = test_validator()
def test_valid_token(): assert V.validate(make_token(roles=["Admin"])).roles == frozenset({"Admin"})
def test_no_roles_claim_means_no_roles(): assert V.validate(make_token()).roles == frozenset()
def test_api_uri_audience_accepted(): V.validate(make_token(aud="api://client-456"))
@pytest.mark.parametrize("o", [{"tid": "other"}, {"iss": "https://login.microsoftonline.com/other/v2.0"},
                               {"aud": "someone-else"}, {"exp": int(time.time()) - 3600}, {"oid": None}])
def test_rejected_401(o):
    with pytest.raises(UnauthorizedError): V.validate(make_token(**o))
def test_bad_signature_401(): ...  # signed with another key
def test_guest_403():
    with pytest.raises(ForbiddenError, match="Guest"): V.validate(make_token(acct=1))
def test_missing_acct_403_and_logged(caplog):
    with pytest.raises(ForbiddenError): V.validate(make_token(acct=None))
    assert "acct optional claim" in caplog.text

def test_me_requires_token(client):
    r = client.get("/api/v1/me"); assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"
def test_me_creates_user_and_returns_profile(client, auth_header, db_session):
    assert client.get("/api/v1/me", headers=auth_header()).json() == {
        "id": ANY, "email": "alice@org", "display_name": "Alice", "roles": [], "is_admin": False}
    assert UserRepository(db_session).get_by_oid("oid-alice") is not None
def test_me_admin(client, admin_header): assert client.get("/api/v1/me", headers=admin_header).json()["is_admin"]
def test_guest_gets_403(client, auth_header): assert client.get("/api/v1/me", headers=auth_header(acct=1)).status_code == 403
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run — expect PASS; ruff clean.**
- [ ] **Step 5: Commit** — `feat(backend): Entra token validation, guest blocking, /me`

---

### Task 5: LLM provider layer

**Files:**
- Create: `backend/app/llm/__init__.py`, `base.py`, `groq_provider.py`, `factory.py`
- Modify: `backend/app/api/deps.py`
- Test: `backend/tests/fakes.py`, `backend/tests/llm/test_groq_provider.py`, `backend/tests/llm/test_factory.py`

**Interfaces:**
- Consumes: `Settings`, LLM errors.
- Produces:
  - `llm.base.ChatMessage(role: Literal["system", "user", "assistant"], content: str)`; `LLMResponse(content: str, model: str, prompt_tokens: int | None, completion_tokens: int | None)`.
  - `llm.base.LLMProvider` (ABC): `name: str`, `default_model: str`; `chat(messages: Sequence[ChatMessage], *, model=None, temperature=None, max_tokens=None) -> LLMResponse`; `stream_chat(<same>) -> Iterator[str]`. Raise only `LLMRateLimitError` / `LLMTimeoutError` / `LLMUnavailableError` on provider failure, including during stream iteration.
  - `GroqProvider(api_key, default_model, temperature, max_tokens, timeout, client: groq.Groq | None = None)`, `name = "groq"`. `groq.RateLimitError` → `LLMRateLimitError("The AI service rate limit was reached. Please wait and try again.")`; `groq.APITimeoutError` → `LLMTimeoutError`; other `groq.APIError` → `LLMUnavailableError`. One INFO line per call: `llm provider=groq model=%s prompt_tokens=%s completion_tokens=%s latency_ms=%d ok=%s` (streams log at end; usage from final chunk `x_groq.usage` if present).
  - `llm.factory.get_llm_provider(settings) -> LLMProvider`, registry dict `{"groq": _build_groq}`; unknown → `ValueError(f"Unknown LLM_PROVIDER: {name!r}")`.
  - `deps.get_llm() -> LLMProvider` (lru_cache).
  - `tests/fakes.py`: `FakeLLMProvider(reply="Hello!", chunks=None, error=None, fail_after=None)`, `name="fake"`, `default_model="fake-model"`, `calls: list[list[ChatMessage]]`; `chat` → `LLMResponse(reply, "fake-model", 5, 7)` or raises `error`; `stream_chat` raises `error` before the first chunk, or yields `chunks` (default `[reply]`) and raises `LLMUnavailableError` after `fail_after` chunks. Conftest: `fake_llm` fixture, `client` overrides `get_llm`.

- [ ] **Step 1: Write failing tests** (mock `groq.Groq` client)

```python
def test_chat_returns_content_and_usage(): ...  # → LLMResponse("hi", "m", 3, 4)
def test_chat_uses_defaults_and_overrides(): ...  # create() kwargs model/temperature/max_tokens
def test_rate_limit_mapped():
    client.chat.completions.create.side_effect = groq.RateLimitError(
        "rl", response=httpx.Response(429, request=httpx.Request("POST", "https://x")), body=None)
    with pytest.raises(LLMRateLimitError): p.chat(msgs)
def test_timeout_mapped(): ...            # APITimeoutError → LLMTimeoutError
def test_connection_error_mapped(): ...   # APIConnectionError → LLMUnavailableError
def test_stream_yields_text_and_skips_empty_deltas(): ...  # "He", None, "llo" → ["He", "llo"]
def test_error_during_stream_iteration_mapped(): ...
def test_log_line_has_no_content(caplog): ...  # "SECRET-PROMPT" not in caplog.text; "provider=groq" in it
def test_factory_groq_and_unknown(): ...
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run — expect PASS; ruff clean.**
- [ ] **Step 5: Commit** — `feat(backend): swappable LLM provider layer with Groq`

---

### Task 6: Document parsing, chunking, file storage

**Files:**
- Create: `backend/app/rag/__init__.py`, `backend/app/rag/parsing.py`, `backend/app/rag/chunking.py`, `backend/app/rag/storage.py`
- Test: `backend/tests/rag/test_parsing.py`, `test_chunking.py`, `test_storage.py`

**Interfaces:**
- Produces:
  - `rag.parsing.SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}`; `ParsedPage(page: int | None, text: str)` dataclass; `DocumentParseError(Exception)`; `parse_document(path: Path, extension: str) -> list[ParsedPage]`. PDF: `pypdf`, one entry per page, `page` 1-based. DOCX: `python-docx` paragraphs joined by `"\n"`, single entry `page=None`. TXT/MD: decode `utf-8-sig`, `errors="replace"`, single entry `page=None`. Whitespace-only pages dropped. Unsupported extension or library failure → `DocumentParseError("Could not read this file")`.
  - `rag.chunking.Chunk(text: str, page: int | None, index: int)`; `chunk_pages(pages: Sequence[ParsedPage], size: int, overlap: int) -> list[Chunk]` — `ValueError` unless `0 <= overlap < size`; per page, fixed character windows of `size` starting every `size - overlap` characters (last window may be shorter, a window fully contained in the previous one is skipped), stripped, empty skipped; never crosses pages; `index` sequential across the whole document from 0.
  - `rag.storage.FileStorage(root: str)`: `save(data: bytes, extension: str) -> str` (creates root, returns generated name `uuid4().hex + extension`), `path(name: str) -> Path` (rejects names containing path separators with `ValueError`), `delete(name: str) -> None` (missing is fine).

- [ ] **Step 1: Write failing tests** (PDFs built in-test with `reportlab`, DOCX with `python-docx`)

```python
def test_pdf_pages_numbered(tmp_path):  # 2-page PDF "alpha" / "beta"
    assert [(p.page, p.text.strip()) for p in parse_document(pdf, ".pdf")] == [(1, "alpha"), (2, "beta")]
def test_docx_paragraphs(tmp_path): ...  # ["one", "two"] → [ParsedPage(None, "one\ntwo")]
def test_txt_utf8_and_md(tmp_path): ...  # "नमस्ते world" round-trips; .md same path
def test_blank_pdf_returns_no_pages(tmp_path): ...  # page with no text → []
def test_corrupt_pdf_raises(tmp_path):
    with pytest.raises(DocumentParseError): parse_document(bad, ".pdf")

def test_chunk_windows_and_overlap():
    text = "".join(chr(97 + i % 26) for i in range(2500))
    chunks = chunk_pages([ParsedPage(1, text)], size=1000, overlap=150)
    assert [len(c.text) for c in chunks] == [1000, 1000, 800]
    assert chunks[0].text[-150:] == chunks[1].text[:150] and [c.index for c in chunks] == [0, 1, 2]
def test_chunks_never_cross_pages(): ...  # two short pages → 2 chunks with pages 1, 2, indexes 0, 1
def test_invalid_overlap_raises(): ...      # overlap=1000, size=1000 → ValueError

def test_storage_creates_root_and_round_trips(tmp_path):
    s = FileStorage(str(tmp_path / "data" / "uploads")); name = s.save(b"hi", ".txt")
    assert name.endswith(".txt") and s.path(name).read_bytes() == b"hi"
    s.delete(name); s.delete(name); assert not s.path(name).exists()
def test_storage_rejects_path_names(tmp_path):
    with pytest.raises(ValueError): FileStorage(str(tmp_path)).path("../x.txt")
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run — expect PASS; ruff clean.**
- [ ] **Step 5: Commit** — `feat(backend): document parsing, chunking and file storage`

---

### Task 7: Embedding provider and vector store (Pinecone) + fakes

**Files:**
- Create: `backend/app/rag/embeddings/__init__.py`, `base.py`, `pinecone_embeddings.py`, `factory.py`; `backend/app/rag/vectorstore/__init__.py`, `base.py`, `pinecone_store.py`, `factory.py`
- Modify: `backend/app/api/deps.py`, `backend/tests/fakes.py`, `backend/tests/conftest.py`
- Test: `backend/tests/rag/test_pinecone_embeddings.py`, `test_pinecone_store.py`, `test_fakes.py`

**Interfaces:**
- Consumes: `Settings`, `VectorStoreUnavailableError`.
- Produces:
  - `embeddings.base.EmbeddingProvider` (ABC): `name: str`, `dimension: int`; `embed_documents(texts: Sequence[str]) -> list[list[float]]`; `embed_query(text: str) -> list[float]`.
  - `PineconeEmbeddingProvider(client: pinecone.Pinecone, model: str, dimension: int, batch_size: int = 96)`: `client.inference.embed(model=model, inputs=batch, parameters={"input_type": "passage" | "query", "truncate": "END"})`, vectors from each item's `values`. Any exception from the SDK → `VectorStoreUnavailableError("Document search service is unavailable")`. Log line `embed provider=pinecone model=%s count=%d latency_ms=%d ok=%s`.
  - `vectorstore.base.VectorRecord(id: str, values: list[float], metadata: dict[str, Any])`; `VectorMatch(id: str, score: float, metadata: dict[str, Any])`; `VectorStore` (ABC): `ensure_index() -> None`, `upsert(namespace: str, records: Sequence[VectorRecord]) -> None`, `query(namespace: str, vector: Sequence[float], top_k: int, filter: dict[str, Any] | None = None) -> list[VectorMatch]`, `delete_by_prefix(namespace: str, prefix: str) -> None`, `ping() -> bool`.
  - `PineconeVectorStore(client, index_name: str, dimension: int, cloud: str, region: str)`: `ensure_index` → `if not client.has_index(name): client.create_index(name=name, dimension=dimension, metric="cosine", spec=ServerlessSpec(cloud=cloud, region=region))`; every other op calls `ensure_index` once lazily (guarded by a lock, retried on later calls if it failed). `upsert` batches of 100; `query(..., include_metadata=True)`; `delete_by_prefix` → `for ids in index.list(prefix=prefix, namespace=ns): index.delete(ids=ids, namespace=ns)`; `ping` → `describe_index` succeeds → True, else False (never raises). SDK exceptions → `VectorStoreUnavailableError`. Log line per call with op, namespace, count, latency.
  - Factories: `get_embedding_provider(settings) -> EmbeddingProvider`, `get_vector_store(settings) -> VectorStore` (registries keyed by `EMBEDDING_PROVIDER` / `VECTOR_STORE_PROVIDER`; unknown → `ValueError`); both share one `pinecone.Pinecone(api_key=...)` client built in `app/rag/pinecone_client.py: get_pinecone_client(api_key: str)` (lru_cache).
  - `deps.get_embeddings()`, `deps.get_vector_store()` (lru_cache).
  - `tests/fakes.py`: `FakeEmbeddingProvider(dimension=64)` — deterministic bag-of-words: lowercase word tokens hashed (`zlib.crc32`) into `dimension` buckets, L2-normalised (texts sharing words score high, unrelated ~0); `fail: bool = False` → raises `VectorStoreUnavailableError`. `FakeVectorStore` — dict `namespace → id → (values, metadata)`; cosine scores; `filter` supports `{"k": {"$eq": v}}` and `{"k": v}`; returns top_k by score desc; `available: bool = True` (False → every op except `ping` raises `VectorStoreUnavailableError`, `ping` returns False); records `queries: list[tuple[str, dict | None]]`; helpers `ids(namespace) -> set[str]`, `metadata(namespace, id) -> dict`. Conftest fixtures `fake_embeddings`, `fake_vector_store`; `client` overrides `get_embeddings` / `get_vector_store`.

- [ ] **Step 1: Write failing tests** (mock Pinecone client)

```python
def test_embed_documents_batches_and_passage_mode():
    p = PineconeEmbeddingProvider(client, "multilingual-e5-large", 1024, batch_size=96)
    p.embed_documents([f"t{i}" for i in range(200)])
    calls = client.inference.embed.call_args_list
    assert [len(c.kwargs["inputs"]) for c in calls] == [96, 96, 8]
    assert all(c.kwargs["parameters"]["input_type"] == "passage" for c in calls)
def test_embed_query_uses_query_mode(): ...
def test_embed_error_mapped(): ...  # side_effect Exception → VectorStoreUnavailableError

def test_ensure_index_creates_when_missing(): ...  # has_index False → create_index(name, dimension=1024, metric="cosine", spec=ServerlessSpec("aws","us-east-1"))
def test_ensure_index_skips_when_present(): ...
def test_query_passes_namespace_filter_and_maps_matches(): ...
def test_delete_by_prefix_deletes_each_page(): ...  # list yields [["doc-1#0","doc-1#1"], ["doc-1#2"]] → 2 delete calls
def test_ping_false_on_error_never_raises(): ...
def test_sdk_error_mapped(): ...  # upsert raises → VectorStoreUnavailableError

def test_fake_store_honours_filter_and_ranking():
    s, e = FakeVectorStore(), FakeEmbeddingProvider()
    s.upsert("personal", [VectorRecord("a", e.embed_query("sprint plan"), {"owner_oid": "A"}),
                          VectorRecord("b", e.embed_query("sprint plan"), {"owner_oid": "B"})])
    hits = s.query("personal", e.embed_query("sprint plan"), 5, {"owner_oid": {"$eq": "A"}})
    assert [h.id for h in hits] == ["a"] and hits[0].score > 0.99
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run — expect PASS; ruff clean.**
- [ ] **Step 5: Commit** — `feat(backend): embedding and vector store interfaces with Pinecone`

---

### Task 8: Retrieval service, document service and routes, startup, health

**Files:**
- Create: `backend/app/services/retrieval_service.py`, `backend/app/services/document_service.py`, `backend/app/api/schemas/document.py`, `backend/app/api/v1/routes/documents.py`
- Modify: `backend/app/api/deps.py`, `backend/app/main.py`, `backend/app/api/v1/routes/health.py`, `backend/tests/test_app.py` (health shape), `backend/tests/conftest.py`
- Test: `backend/tests/services/test_retrieval_service.py`, `backend/tests/services/test_document_service.py`, `backend/tests/api/test_documents.py`, `backend/tests/test_startup.py`

**Interfaces:**
- Consumes: `DocumentRepository`, `FileStorage`, `parse_document`, `chunk_pages`, `SUPPORTED_EXTENSIONS`, `EmbeddingProvider`, `VectorStore`, `VectorRecord`, `CurrentUser`, `DocumentScope`, errors, fakes.
- Produces:
  - `retrieval_service.vector_location(scope: DocumentScope, owner_oid: str) -> tuple[str, dict[str, Any] | None]` → `("personal", {"owner_oid": {"$eq": owner_oid}})` or `("company", None)`. The only place namespaces/filters are built.
  - `RetrievedChunk(document_id: int, filename: str, page: int | None, text: str, score: float)`.
  - `RetrievalService(embeddings, vector_store, top_k: int, min_score: float)`: `search(user: CurrentUser, scope: DocumentScope, query: str, top_k: int | None = None) -> list[RetrievedChunk]` — embed query, query namespace with filter, drop `score < min_score`, keep order.
  - `DocumentService(documents: DocumentRepository, storage: FileStorage, embeddings, vector_store, chunk_size: int, chunk_overlap: int, max_upload_bytes: int)`:
    - `upload(user, scope, filename: str, content_type: str, data: bytes) -> Document` — company and not admin → `ForbiddenError("Only admins can manage company documents")`; display name = `PureWindowsPath(filename).name` (handles `/` and `\`), fallback `"document"`; extension (lowercased) not in `SUPPORTED_EXTENSIONS` → `UnsupportedFileTypeError("Supported file types: PDF, DOCX, TXT, MD")`; `len(data) > max_upload_bytes` → `FileTooLargeError(f"File is larger than {max_upload_bytes // (1024*1024)} MB")`; save via storage; create row (status `processing`).
    - `process(document_id: int, owner_oid: str) -> None` — never raises. Loads row (missing → `delete_by_prefix` best effort, return). Parse → chunk → no chunks → `mark_failed("No text found in this file (scanned PDFs are not supported)")`. Embed (`embed_documents`) → records `VectorRecord(f"doc-{id}#{c.index}", values, {"document_id", "owner_oid", "filename", "chunk_index", "text"} + "page" only when not None)` → `upsert` into `vector_location(scope, owner_oid)[0]` (company docs also carry `owner_oid` = uploader, harmless). Re-load row after upsert; if it was deleted meanwhile → `delete_by_prefix` and return. Else `mark_ready(chunk_count)`. On failure: best-effort `delete_by_prefix(ns, f"doc-{id}#")`, `mark_failed` with `DocumentParseError` → its message; `VectorStoreUnavailableError` → `"Document search service is unavailable; please try again later"`; anything else → `"Processing failed"` (traceback logged). Logs id, scope, pages, chunks, ms.
    - `list_documents(user, scope) -> list[Document]` (personal: own; company: all).
    - `get_document(user, document_id) -> Document` — missing or someone else's personal → `NotFoundError("Document not found")`.
    - `delete_document(user, document_id) -> None` — someone else's personal → `NotFoundError`; company and not admin → `ForbiddenError`; then `delete_by_prefix` (raises `VectorStoreUnavailableError` and keeps the row so the user can retry), `storage.delete`, `documents.delete`.
    - `fail_interrupted() -> int` → `fail_all_processing("Processing was interrupted; please upload again")`.
  - `deps`: `get_file_storage() -> FileStorage` (from `UPLOAD_DIR`), `get_retrieval_service(...)`, `get_document_service(db, ...)`, `build_document_processor(session_factory, storage, embeddings, vector_store, settings) -> Callable[[int, str], None]` — returns a function that opens a new session from `session_factory`, builds a `DocumentService`, calls `process`, closes the session (the request session is gone by the time background tasks run).
  - Schemas: `DocumentRead{id, scope, filename, content_type, size_bytes, status, error_message, chunk_count, created_at, updated_at}`.
  - Routes (all `get_current_user`): `POST /api/v1/documents` (multipart `file: UploadFile`, `scope: DocumentScope = Form(...)`) → 202 `DocumentRead`; reads at most `max_upload_bytes + 1` bytes from `file.file` and passes them to `upload`; schedules `background_tasks.add_task(processor, doc.id, user.entra_oid)`. `GET /api/v1/documents?scope=` → `list[DocumentRead]`; `GET /api/v1/documents/{id}`; `DELETE /api/v1/documents/{id}` → 204.
  - `main.run_startup_tasks(session_factory, vector_store) -> None`: `fail_interrupted()` via a `DocumentService`-free path (a `DocumentRepository` on a new session), then `vector_store.ensure_index()` inside `try/except Exception` → log ERROR `"Vector store not ready: %s"` and continue. Called from the FastAPI lifespan only when `create_app(run_startup=True)`.
  - Health → `{"status": "ok", "database": "ok", "vector_store": "ok" | "error"}`; 200 unless the database fails (503).
  - Conftest: `client` overrides `get_file_storage` with a tmp `FileStorage`; fixtures `doc_service(user)` etc. as needed. TestClient runs background tasks before returning, so uploads in API tests are processed synchronously.

- [ ] **Step 1: Write failing service tests** (real repos on the test DB, fakes for embeddings/vector store, tmp storage, `chunk_size=1000`, `chunk_overlap=150`, `max_upload_bytes=1024*1024`, `min_score=0.5`)

```python
def test_upload_and_process_personal_txt(svc, alice, fake_vector_store):
    doc = svc.upload(alice, "personal", "notes.txt", "text/plain", b"Sprint plan for project Apollo")
    assert doc.status == "processing"
    svc.process(doc.id, alice.entra_oid)
    doc = svc.get_document(alice, doc.id)
    assert (doc.status, doc.chunk_count) == ("ready", 1)
    assert fake_vector_store.ids("personal") == {f"doc-{doc.id}#0"}
    assert fake_vector_store.metadata("personal", f"doc-{doc.id}#0")["owner_oid"] == "oid-alice"

def test_company_upload_requires_admin(svc, alice): ...  # ForbiddenError
def test_unsupported_type_and_too_large(svc, alice): ...  # "x.exe" → UnsupportedFileTypeError; 1 MB + 1 → FileTooLargeError
def test_upload_filename_is_sanitised(svc, alice, storage_root):
    doc = svc.upload(alice, "personal", "..\\..\\evil.pdf", "application/pdf", PDF_BYTES)
    assert doc.filename == "evil.pdf" and Path(storage_root, doc.storage_path).parent == Path(storage_root)
    assert svc.upload(alice, "personal", "प्रोजेक्ट.txt", "text/plain", b"x").filename == "प्रोजेक्ट.txt"
def test_empty_text_marks_failed(svc, alice): ...  # blank PDF → status failed, message mentions "scanned PDFs"
def test_vector_store_down_marks_failed_no_vectors(svc, alice, fake_vector_store): ...
def test_process_after_delete_leaves_no_vectors(svc, alice, fake_vector_store):
    doc = svc.upload(alice, "personal", "a.txt", "text/plain", b"hello world")
    svc.delete_document(alice, doc.id)
    svc.process(doc.id, alice.entra_oid)   # must not raise
    assert fake_vector_store.ids("personal") == set()
def test_delete_removes_vectors_file_and_row(svc, alice, fake_vector_store, storage_root): ...
def test_other_users_personal_doc_is_not_found(svc, alice, bob): ...  # get/delete → NotFoundError; list_documents(bob, "personal") == []
def test_company_delete_requires_admin(svc, admin, alice): ...  # admin uploads; alice delete → ForbiddenError
def test_fail_interrupted(svc, alice): ...  # 2 processing → returns 2

# test_retrieval_service.py
def test_personal_search_never_returns_other_users_chunks(retrieval, alice, bob, indexed):  # both index "apollo sprint"
    assert {c.document_id for c in retrieval.search(bob, "personal", "apollo sprint")} == {indexed.bob_doc_id}
    assert fake_vector_store.queries[-1] == ("personal", {"owner_oid": {"$eq": "oid-bob"}})
def test_company_search_has_no_filter(...): ...
def test_low_scores_dropped(...): ...  # unrelated query → []
```

- [ ] **Step 2: Write failing API / startup tests**

```python
def test_upload_then_ready(client, auth_header):
    r = client.post("/api/v1/documents", data={"scope": "personal"},
                    files={"file": ("n.txt", b"hello apollo", "text/plain")}, headers=auth_header())
    assert r.status_code == 202 and r.json()["status"] == "processing"
    assert client.get(f"/api/v1/documents/{r.json()['id']}", headers=auth_header()).json()["status"] == "ready"
def test_upload_errors(client, auth_header): ...  # .exe → 415 unsupported_file_type; 11 MB → 413 file_too_large
def test_company_upload_forbidden_for_user(client, auth_header): ...  # 403
def test_company_docs_listed_for_everyone(client, admin_header, bob_header): ...
def test_other_users_doc_404(client, auth_header, bob_header): ...
def test_delete_204(client, auth_header): ...
def test_documents_502_when_vector_store_down(client, auth_header, fake_vector_store):
    fake_vector_store.available = False  # upload accepted (202) then status failed; DELETE → 502 vector_store_unavailable
def test_health_reports_vector_store(client, fake_vector_store):
    fake_vector_store.available = False
    r = client.get("/health"); assert r.status_code == 200 and r.json()["vector_store"] == "error"
def test_startup_survives_vector_store_down(session_factory, fake_vector_store, caplog):
    fake_vector_store.available = False
    run_startup_tasks(session_factory, fake_vector_store)  # no exception
    assert "Vector store not ready" in caplog.text
```

Update `test_health_ok` to expect `{"status": "ok", "database": "ok", "vector_store": "ok"}`.

- [ ] **Step 3: Run — expect FAIL.**
- [ ] **Step 4: Implement.**
- [ ] **Step 5: Run full backend suite — expect PASS; ruff clean.**
- [ ] **Step 6: Commit** — `feat(backend): document upload, processing, retrieval and startup checks`

---

### Task 9: Chat service and routes (scoped RAG + streaming)

**Files:**
- Create: `backend/app/services/chat_service.py`, `backend/app/api/schemas/chat.py`, `backend/app/api/v1/routes/chat.py`
- Modify: `backend/app/api/deps.py`, `backend/app/main.py`
- Test: `backend/tests/services/test_chat_service.py`, `backend/tests/api/test_chat.py`

**Interfaces:**
- Consumes: `ConversationRepository`, `MessageRepository`, `LLMProvider`, `ChatMessage`, `RetrievalService`, `RetrievedChunk`, `CurrentUser`, `KnowledgeScope`, fakes.
- Produces:
  - `ChatService(conversations, messages, llm: LLMProvider, retrieval: RetrievalService, system_prompt: str, history_limit: int)`:
    - `create_conversation(user, title: str | None = None, knowledge_scope: KnowledgeScope = "none") -> Conversation` (default title `"New chat"`).
    - `list_conversations(user) -> list[Conversation]`; `get_messages(user, conversation_id) -> list[Message]` (`NotFoundError("Conversation not found")`).
    - `send_message(user, conversation_id, content) -> Message` (assistant message).
    - `start_stream(user, conversation_id, content) -> Iterator[str]`.
  - Context: system message, then last `history_limit` stored messages, then `user(content)`. For `knowledge_scope != "none"`, retrieval runs first (`retrieval.search(user, scope, content)`) and the system message is `system_prompt + "\n\n" + RAG_INSTRUCTIONS + "\n\n" + excerpts`, where:
    - `RAG_INSTRUCTIONS = "Answer using only the numbered document excerpts below. Cite excerpts like [1]. If the excerpts do not contain the answer, say you don't know based on the available documents."`
    - each excerpt is `"[n] (<filename>, page <p>)\n<text>"` (`, page <p>` omitted when page is None), joined by blank lines; with no chunks the excerpts text is `"No documents matched this question."`
    - `sources` = chunks deduplicated by `(document_id, page)` in order, as `{"document_id", "filename", "page"}`; `[]` for scoped chats with no matches, `None` for unscoped chats.
  - Persistence: user + assistant messages saved only after the LLM reply (non-stream) or its first chunk (stream). Any error before that (retrieval `VectorStoreUnavailableError`, LLM errors, 404) leaves the DB untouched. First exchange in a `"New chat"` sets title to the first 60 chars of content with newlines → spaces. Each exchange bumps `updated_at`.
  - `start_stream`: ownership, retrieval, context, `llm.stream_chat`, first chunk pulled **eagerly**; then save user message; generator yields first chunk + rest; on completion saves assistant message (`model=llm.default_model`, tokens None, `sources`); on `AppError` mid-stream logs WARNING, yields `"\n\n[Response interrupted. Please try again.]"`, saves no assistant message; empty stream saves empty assistant message.
  - Schemas: `ConversationCreate{title: str | None (max 200), knowledge_scope: KnowledgeScope = "none"}`, `ConversationRead{id, title, knowledge_scope, created_at, updated_at}`, `MessageCreate{content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]}`, `SourceRead{document_id: int, filename: str, page: int | None}`, `MessageRead{id, role, content, model, sources: list[SourceRead] | None, created_at}`.
  - Routes (all `get_current_user`): `POST /api/v1/conversations` → 201; `GET /api/v1/conversations`; `GET /api/v1/conversations/{id}/messages`; `POST /api/v1/conversations/{id}/messages` → `MessageRead`; `POST /api/v1/conversations/{id}/messages/stream` → `StreamingResponse(media_type="text/plain; charset=utf-8")`, body generator's `finally` calls `db.close()` on the request session (`db=Depends(get_db)`).
  - `deps.get_chat_service(db, llm, retrieval) -> ChatService`.

- [ ] **Step 1: Write failing service tests** (real repos, `FakeLLMProvider`, `RetrievalService` over fakes with `min_score=0.5`)

```python
def test_send_message_persists_exchange_and_titles(svc_factory, alice):
    svc, llm = svc_factory(reply="Hi Alice"); conv = svc.create_conversation(alice)
    reply = svc.send_message(alice, conv.id, "Plan my sprint\nplease")
    assert (reply.role, reply.content, reply.model, reply.sources) == ("assistant", "Hi Alice", "fake-model", None)
    assert svc.list_conversations(alice)[0].title == "Plan my sprint please"
def test_context_has_system_prompt_and_last_n(svc_factory, alice): ...  # history_limit=2 → len == 1 + 2 + 1
def test_other_users_conversation_not_found(svc_factory, alice, bob): ...
def test_send_message_rate_limited_persists_nothing(svc_factory, alice):
    svc, _ = svc_factory(error=LLMRateLimitError("rl")); conv = svc.create_conversation(alice)
    with pytest.raises(LLMRateLimitError): svc.send_message(alice, conv.id, "hi")
    assert svc.get_messages(alice, conv.id) == []
def test_personal_scoped_chat_uses_own_docs_with_sources(svc_factory, alice, bob, indexed_docs):
    # alice and bob each have an indexed personal doc about "apollo sprint"
    svc, llm = svc_factory(); conv = svc.create_conversation(alice, knowledge_scope="personal")
    reply = svc.send_message(alice, conv.id, "apollo sprint")
    system = llm.calls[-1][0].content
    assert "Cite excerpts like [1]" in system and "[1] (alice.txt" in system and "bob.txt" not in system
    assert reply.sources == [{"document_id": indexed_docs.alice_id, "filename": "alice.txt", "page": None}]
def test_scoped_chat_no_match_still_answers(svc_factory, alice, indexed_docs):
    # unrelated question → "No documents matched this question." in system; reply.sources == []
def test_scoped_chat_vector_store_down_persists_nothing(svc_factory, alice, fake_vector_store): ...
def test_unscoped_chat_works_when_vector_store_down(svc_factory, alice, fake_vector_store): ...
def test_stream_completes_and_persists_sources(svc_factory, alice, indexed_docs): ...
def test_stream_error_before_first_chunk_raises_eagerly_and_persists_nothing(svc_factory, alice): ...
def test_stream_interrupted_mid_reply(svc_factory, alice):
    svc, _ = svc_factory(chunks=["Par", "tial", "x"], fail_after=2); conv = svc.create_conversation(alice)
    assert "".join(svc.start_stream(alice, conv.id, "hi")) == "Partial\n\n[Response interrupted. Please try again.]"
    assert [m.role for m in svc.get_messages(alice, conv.id)] == ["user"]
```

- [ ] **Step 2: Write failing API tests**

```python
def test_chat_requires_auth(client): assert client.get("/api/v1/conversations").status_code == 401
def test_create_list_send_flow(client, auth_header): ...  # 201 with knowledge_scope "none" → send → 2 messages
def test_create_with_scope_and_invalid_scope(client, auth_header): ...  # "company" ok; "everything" → 422
def test_other_users_conversation_404(client, auth_header, bob_header): ...
def test_send_message_rejects_blank_and_oversized(client, auth_header, fake_llm):
    for content in ["", "   \n ", "x" * 8001]:
        r = client.post(f"/api/v1/conversations/{cid}/messages", json={"content": content}, headers=h)
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    assert fake_llm.calls == []
def test_send_message_rate_limited_429(client, ...): ...
def test_scoped_chat_502_when_vector_store_down(client, ...): ...  # vector_store_unavailable
def test_stream_returns_text(client, ...): ...  # content-type text/plain; body "Hello"
def test_stream_rate_limited_before_first_chunk_returns_429(client, ...): ...
```

- [ ] **Step 3: Run — expect FAIL.**
- [ ] **Step 4: Implement.**
- [ ] **Step 5: Run full backend suite — expect PASS; ruff clean.**
- [ ] **Step 6: Commit** — `feat(backend): chat with optional document grounding and streaming`

---

### Task 10: Admin service and route

**Files:**
- Create: `backend/app/services/admin_service.py`, `backend/app/api/schemas/admin.py`, `backend/app/api/v1/routes/admin.py`
- Modify: `backend/app/api/deps.py`, `backend/app/main.py`
- Test: `backend/tests/api/test_admin.py`

**Interfaces:**
- Consumes: `UserRepository.list_with_stats`, `UserStats`, `require_admin`.
- Produces: `AdminService(users)`: `list_users() -> list[UserStats]`; `GET /api/v1/admin/users` (`require_admin`) → `list[AdminUserRead{id, email, display_name, created_at, last_seen_at, conversation_count, message_count}]`; `deps.get_admin_service(db)`.

- [ ] **Step 1: Write failing tests**

```python
def test_admin_users_forbidden_for_normal_user(client, auth_header):
    r = client.get("/api/v1/admin/users", headers=auth_header())
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"
def test_admin_users_lists_with_counts(client, auth_header, admin_header):
    # alice creates 1 conversation and sends 1 message via the API
    rows = {u["email"]: u for u in client.get("/api/v1/admin/users", headers=admin_header).json()}
    assert (rows["alice@org"]["conversation_count"], rows["alice@org"]["message_count"]) == (1, 2)
def test_admin_users_requires_token(client): assert client.get("/api/v1/admin/users").status_code == 401
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run — expect PASS; ruff clean.**
- [ ] **Step 5: Commit** — `feat(backend): admin users endpoint`

---

### Task 11: Frontend foundation — settings, logging, API client

**Files:**
- Create: `frontend/pyproject.toml`, `frontend/config.py`, `frontend/logging_setup.py`, `frontend/services/__init__.py`, `frontend/services/api_client.py`
- Test: `frontend/tests/__init__.py`, `frontend/tests/test_api_client.py`, `frontend/tests/test_logging_setup.py`

**Interfaces:**
- Produces:
  - `config.FrontendSettings`: `entra_tenant_id: str`, `entra_client_id: str`, `entra_client_secret: SecretStr`, `entra_api_scope: str`, `entra_redirect_uri: str = "http://localhost:8501"`, `api_base_url: str = "http://localhost:8000"`, `max_upload_mb: int = 10`, `log_level: str = "INFO"`, `log_dir: str = "./logs"`, `log_retention_days: int = 14`; `get_settings()`; same `env_file`/`extra` as backend.
  - `logging_setup.setup_logging(log_dir, level, filename="frontend.log")`, `user_var`, `request_id_var` — same format/handlers as backend (deliberate small copy; the apps share no package).
  - `services.api_client.AuthExpiredError`; `ApiError(code: str, message: str, status: int, request_id: str | None)`.
  - `ApiClient(base_url: str, token_provider: Callable[[], str | None], transport: httpx.BaseTransport | None = None, timeout: float = 120.0)`: `get_me() -> dict`; `list_conversations() -> list[dict]`; `create_conversation(title: str | None = None, knowledge_scope: str = "none") -> dict`; `get_messages(conversation_id: int) -> list[dict]`; `stream_message(conversation_id: int, content: str) -> Iterator[str]`; `list_documents(scope: str) -> list[dict]`; `upload_document(scope: str, filename: str, data: bytes, content_type: str) -> dict`; `delete_document(document_id: int) -> None`; `list_admin_users() -> list[dict]`. Every request: bearer token, `X-Request-ID: uuid4().hex[:12]`, log `"%s %s -> %s (%.0f ms)"`. No token or 401 → `AuthExpiredError`; other non-2xx → `ApiError` from error body (fallback code `f"http_{status}"`); connection failure → `ApiError("backend_unreachable", "Cannot reach the API server", 0, None)`.

- [ ] **Step 1: Init** — in `frontend/`: `uv init --app --python 3.12 --no-readme`, delete generated script, `uv add streamlit msal httpx pydantic-settings`, `uv add --dev pytest ruff`; pytest `testpaths=["tests"]`, `pythonpath=["."]`.

- [ ] **Step 2: Write failing tests** (`httpx.MockTransport`)

```python
def test_sends_bearer_and_request_id(): ...  # authorization == "Bearer tok", len(x-request-id) == 12
def test_401_raises_auth_expired(): ...
def test_missing_token_raises_auth_expired(): ...  # transport never called
def test_error_body_becomes_api_error():
    # 429 {"error": {"code": "llm_rate_limited", "message": "busy", "request_id": "r1"}}
    assert (e.value.code, e.value.status, e.value.request_id) == ("llm_rate_limited", 429, "r1")
def test_stream_message_yields_text(): ...
def test_upload_document_sends_multipart(): ...  # request has scope=personal form field and file part "a.txt"
def test_create_conversation_sends_scope(): ...  # JSON {"title": None, "knowledge_scope": "company"}
def test_connection_error_becomes_backend_unreachable(): ...
def test_frontend_log_format(tmp_path): ...  # same regex as backend, file frontend.log
```

- [ ] **Step 3: Run — expect FAIL.** `cd frontend && uv run pytest -v`
- [ ] **Step 4: Implement.**
- [ ] **Step 5: Run — expect PASS; ruff clean.**
- [ ] **Step 6: Commit** — `feat(frontend): settings, logging, typed API client`

---

### Task 12: Frontend sign-in and pages (chat, documents, admin)

**Files:**
- Create: `frontend/auth/__init__.py`, `frontend/auth/flow_store.py`, `frontend/auth/entra.py`, `frontend/auth/session.py`, `frontend/app.py`, `frontend/views/common.py`, `frontend/views/chat.py`, `frontend/views/documents.py`, `frontend/views/admin.py`, `frontend/.streamlit/config.toml`
- Test: `frontend/tests/test_flow_store.py`, `frontend/tests/test_entra.py`, `frontend/tests/test_common.py`

(Pages live in `views/` and are registered with `st.navigation`, so Streamlit's automatic `pages/` sidebar can't list the admin page to non-admins.)

**Interfaces:**
- Consumes: `FrontendSettings`, `ApiClient`, `AuthExpiredError`, `ApiError`, `setup_logging`, `user_var`.
- Produces:
  - `auth.flow_store.PendingFlowStore(ttl_seconds: float = 600, clock=time.monotonic)`: `put(state, flow)`, `pop(state) -> dict | None` (single use, expired → None, purges on each call, `threading.Lock`). One process-wide instance via `st.cache_resource`, because the Microsoft redirect starts a new Streamlit session.
  - `auth.entra.AuthError(Exception)`; `EntraAuth(settings, store, msal_app_factory: Callable[[msal.TokenCache], msal.ConfidentialClientApplication] | None = None)`:
    - `build_login_url() -> str` — `initiate_auth_code_flow(scopes=[settings.entra_api_scope], redirect_uri=settings.entra_redirect_uri)`, store by `flow["state"]`, return `flow["auth_uri"]` (no reserved scopes passed).
    - `complete_login(query_params: Mapping[str, str]) -> str` — pop flow (missing → `AuthError("Sign-in expired, please try again")`), `acquire_token_by_auth_code_flow` into a fresh `msal.SerializableTokenCache`; `"error"` in result → `AuthError(result["error_description"])`; return `cache.serialize()`.
    - `get_access_token(cache_blob: str) -> tuple[str | None, str]` — `acquire_token_silent([scope], account=first account)`.
    - `logout_url() -> str` — `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/logout?post_logout_redirect_uri=<urlencoded>`.
    - Authority `https://login.microsoftonline.com/{tenant_id}`.
  - `auth.session` (Streamlit glue): `require_login()` (handles `code`/`state` query params → `complete_login` → `st.session_state["token_cache"]` → clear params → `st.rerun()`; not signed in → title + "Sign in with Microsoft" link with `target="_self"` → `st.stop()`; `AuthError` → `st.error` + link), `current_token() -> str | None`, `sign_out()` (clear state, same-tab redirect to `logout_url()`).
  - `views.common`: `friendly_error(e: ApiError) -> str` — `llm_rate_limited` → "The AI service is busy right now (rate limit). Please wait a moment and try again."; `vector_store_unavailable` → "Document search is unavailable right now. Please try again later."; `backend_unreachable` → "Cannot reach the API server."; `forbidden` → "You don't have permission to do that."; otherwise `e.message`; appends `" (ref: <request_id>)"` when present. `call_api(fn, *args, **kwargs)` — runs `fn`; `AuthExpiredError` → clear session state + `st.rerun()`; `ApiError` → `st.error(friendly_error(e))`, returns None. `SCOPE_LABELS = {"none": "No documents", "personal": "My documents", "company": "Company documents"}`.
  - `app.py`: `st.set_page_config(page_title="GenAI App")`, `setup_logging`, `require_login()`, one `ApiClient(settings.api_base_url, current_token)` per session, `get_me()` into `st.session_state["me"]`, `user_var`, sidebar name + "Sign out", `st.navigation([Chat (default), Documents] + ([Admin] if me["is_admin"] else []))`.
  - `views/chat.py`: sidebar "New chat" with a `st.selectbox` over `SCOPE_LABELS` → `create_conversation(knowledge_scope=...)`; conversation list newest first labelled `"<title> · <scope label>"`; history via `st.chat_message`, assistant messages with `sources` show a "Sources" caption list `filename (page p)`; `st.chat_input` → user bubble, `st.write_stream(api.stream_message(...))`, then re-fetch messages to show the saved sources.
  - `views/documents.py`: tabs "My documents" / "Company documents"; `st.file_uploader(type=["pdf", "docx", "txt", "md"])` + Upload button (company tab: only when `me["is_admin"]`); table of filename, status, chunks, uploaded at, error message; "Refresh" button; delete per row with a confirm checkbox/button (company tab: admins only).
  - `views/admin.py`: `st.dataframe` of `list_admin_users()`.
  - `.streamlit/config.toml`: `[server] headless = true`, `maxUploadSize = 10`; `[browser] gatherUsageStats = false`.

- [ ] **Step 1: Write failing tests**

```python
def test_pop_is_single_use():
    s = PendingFlowStore(); s.put("st", {"a": 1}); assert s.pop("st") == {"a": 1} and s.pop("st") is None
def test_expired_flow_is_gone():
    t = [0.0]; s = PendingFlowStore(ttl_seconds=10, clock=lambda: t[0]); s.put("st", {}); t[0] = 11
    assert s.pop("st") is None
def test_build_login_url_stores_flow_and_requests_api_scope(): ...  # msal mock via msal_app_factory
def test_complete_login_unknown_state_raises(): ...
def test_complete_login_error_result_raises(): ...  # error_description "denied" → AuthError("denied")
def test_get_access_token_none_when_no_account(): ...
def test_logout_url_encodes_redirect(): ...
def test_friendly_error_messages():
    assert friendly_error(ApiError("llm_rate_limited", "x", 429, "r1")).endswith("(ref: r1)")
    assert friendly_error(ApiError("other", "Boom", 500, None)) == "Boom"
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement all files above.**
- [ ] **Step 4: Run frontend suite — expect PASS; ruff clean.**
- [ ] **Step 5: Manual check (needs a real app registration, Groq key and Pinecone key in `.env`; skip and report if unavailable)**

Backend: `cd backend && uv run alembic upgrade head && uv run uvicorn app.main:app --port 8000`. Frontend: `cd frontend && uv run streamlit run app.py`. Expected: sign-in → chat streams a reply; upload a PDF in "My documents" → refresh shows `ready`; new chat with "My documents" answers from it and lists sources; a second user can't see the first user's documents; non-admin can't upload company documents and sees no Admin page; Sign out returns to sign-in; logs show matching `req=` ids and no message or document text.

- [ ] **Step 6: Commit** — `feat(frontend): Entra sign-in, chat, documents and admin pages`

---

### Task 13: Docker, `.env.example`, README

**Files:**
- Create: `backend/Dockerfile`, `frontend/Dockerfile`, `backend/.dockerignore`, `frontend/.dockerignore`, `docker-compose.yml`, `.env.example`, `README.md`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - Dockerfiles: `python:3.12-slim`, `uv` binary copied from `ghcr.io/astral-sh/uv` (pinned tag), `uv sync --frozen --no-dev`, non-root user, `WORKDIR /app`. Backend `CMD sh -c "uv run --no-sync alembic upgrade head && uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port 8000"`. Frontend `CMD uv run --no-sync streamlit run app.py --server.address 0.0.0.0 --server.port 8501`.
  - `docker-compose.yml`: `backend` (8000, `env_file: .env`, `DATABASE_URL=sqlite:////app/data/app.db`, `UPLOAD_DIR=/app/data/uploads`, `LOG_DIR=/app/logs`, volumes `app-data:/app/data`, `app-logs:/app/logs`, healthcheck on `/health`); `frontend` (8501, `env_file: .env`, `API_BASE_URL=http://backend:8000`, `LOG_DIR=/app/logs`, volume `app-logs`, `depends_on: backend: condition: service_healthy`). Non-root user owns `/app/data` and `/app/logs`.
  - `.env.example`: every key from both settings classes, one comment line each; `ENTRA_API_SCOPE=api://<client-id>/access_as_user`, `ENTRA_REDIRECT_URI=http://localhost:8501`, `LLM_MODEL=llama-3.3-70b-versatile` (Groq model names change), Pinecone keys with defaults.
  - `README.md`: overview + text architecture diagram; Quick start (Docker); local run on Windows (two terminals, `uv sync`, `alembic upgrade head`); Entra walkthrough (single-tenant registration; Web redirect URI; client secret; Expose an API → `access_as_user`; Manifest `requestedAccessTokenVersion: 2`; Token configuration → optional claim `acct` on the access token; App role `Admin` and assigning admins in Enterprise applications; "Assignment required" can be switched on later); Pinecone setup (free account, API key, index created automatically, one index per app, free-tier index limit, `RAG_MIN_SCORE` tuning); `.env` reference; layout + layering rules; how to add a feature (route → schema → service → repo → migration); how to add an LLM provider / embedding provider / vector store; how a feature uses `RetrievalService.search` with a personal or company scope; removing document Q&A from an app (files and settings to delete); switching SQLite → Postgres; logging (format, location, retention, never-logged list); tests and lint.

- [ ] **Step 1: Write files.**
- [ ] **Step 2: Verify** — `docker compose config` exits 0. If Docker is installed: `docker compose build` succeeds; with a filled `.env`, `docker compose up -d` → `curl http://localhost:8000/health` returns `{"status":"ok","database":"ok","vector_store":"ok"}`. If Docker isn't available, say so in the report.
- [ ] **Step 3: Final checks** — `cd backend && uv run pytest && uv run ruff check .`; `cd frontend && uv run pytest && uv run ruff check .` all pass.
- [ ] **Step 4: Commit** — `chore: docker setup, env example, README`
