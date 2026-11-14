# GenAI Boilerplate — Design

Date: 2026-10-24
Status: Approved 2026-10-24 (including document Q&A, §5.13)

## 1. Intent

A starter repository the team copies to begin each new GenAI application. It contains
no business features; it contains the wiring every GenAI app needs, working end to end
on first run:

- Microsoft Entra ID sign-in, restricted to the organisation's tenant, with an Admin role
- A Streamlit frontend talking to a FastAPI backend
- A FastAPI backend organised strictly as **api → service → repo** layers
- A SQLite database behind an abstraction that can later move to another SQL database
- A swappable LLM layer, Groq by default
- Document Q&A (RAG): upload documents, store embeddings in a vector database (Pinecone by
  default, swappable), and chat answers grounded in either a user's personal documents or
  the company's shared documents
- Docker setup, plain-text file logging, tests

**Why:** the team is about to build several GenAI apps (the first planned one is an AI
project-management assistant: problem statements, sprint plans, task breakdowns, test
cases, a chatbot for daily updates, notifications). None of that is in scope here. The
boilerplate exists so each new app starts from a known-good, consistent base instead of
re-solving auth, layering, LLM access and setup every time.

## 2. Goals

1. Clone, fill in `.env`, run `docker compose up` (or run both apps locally) → sign in with
   a Microsoft work account → chat with the LLM → conversation is saved and listed.
2. Clear, enforced layering in the backend that new features copy by example.
3. Changing LLM provider/model is a config change plus, at most, one new provider class.
   Services never import a vendor SDK directly.
4. Changing the database from SQLite to e.g. Postgres is a connection-string change plus
   a driver install; repo code is unchanged.
5. The API is secure on its own: every request is authenticated by validating the Entra
   token, regardless of what the frontend does.
6. Upload a document → it is processed and searchable → a chat set to that collection
   answers from it and shows sources. A user can never retrieve another user's personal
   documents.
7. Changing vector store or embedding provider is a config change plus, at most, one new
   class each. Services never import the Pinecone SDK directly.

## 3. Non-goals

- Any project-management features (inputs, generation, chatbot-updates, notifications).
- Deployment scripts or infrastructure for any specific host (target is undecided).
- A CI pipeline.
- Supabase (explicitly dropped).
- A local "skip login" / fake-user mode.
- Multi-tenant support. Guest (B2B) accounts are actively blocked, not merely unsupported (§5.4).
- Logging of prompt/response contents (or document contents).
- OCR of scanned PDFs/images; file types beyond PDF, DOCX, TXT, MD.
- A chat that searches personal and company documents at the same time (user: each
  feature uses one collection).
- Job queues/workers for document processing (in-process background tasks are enough).

## 4. Anti-goals (would make this a failure even if it runs)

- Business logic in routes, or database access outside repos.
- Vendor SDK calls (Groq, OpenAI…) scattered in services.
- The API trusting the frontend for identity or role (e.g. a user-id header).
- Admin-only endpoints reachable by non-admins.
- Any path where one user's personal document chunks reach another user's chat or listing.
- Over-engineered abstractions that make a simple new feature take many files of ceremony
  beyond the three layers.

## 5. Decisions

Marked **(user)** where the user decided, **(my call)** where I decided and the user can override.

### 5.1 Stack

| Concern | Choice |
|---|---|
| Frontend | Streamlit **(user)** |
| Backend | FastAPI **(user)** |
| Database | SQLite **(user)**, via SQLAlchemy 2.x ORM + Alembic migrations **(my call)** |
| LLM | Groq default **(user)**, behind a provider interface **(user: "switch to any later")** |
| Auth | Microsoft Entra ID, single tenant **(user)** |
| Roles | Admin via Entra App Roles **(user)** |
| Vector DB | Pinecone (serverless) **(user)**, behind a `VectorStore` interface **(my call)** |
| Embeddings | Pinecone hosted inference, `multilingual-e5-large` (1024 dims) **(my call)**, behind an `EmbeddingProvider` interface |
| Document parsing | `pypdf` (PDF), `python-docx` (DOCX), UTF-8 decode (TXT/MD) **(my call)** |
| Containers | Docker + docker compose **(user)** |
| Python | 3.12 **(my call)** |
| Dependencies | `uv` with `pyproject.toml` **(my call)** |
| Lint/format | Ruff **(my call)** |
| Tests | pytest **(my call)** |
| Config | pydantic-settings reading `.env` **(my call)** |

### 5.2 Repository layout (my call)

Single repo, two apps, one shared `pyproject.toml` with dependency groups (or two
projects — builder's choice, see §7).

```
.
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app factory, middleware, exception handlers
│   │   ├── core/
│   │   │   ├── config.py        # Settings (pydantic-settings)
│   │   │   ├── logging.py       # Text logging setup
│   │   │   ├── security.py      # Entra token validation, current-user + require-admin deps
│   │   │   └── errors.py        # App exception types → JSON error responses
│   │   ├── db/
│   │   │   ├── base.py          # SQLAlchemy engine, session, Base
│   │   │   └── models/          # ORM models
│   │   ├── api/
│   │   │   ├── deps.py          # Dependency wiring (session → repo → service)
│   │   │   ├── schemas/         # Pydantic request/response models
│   │   │   └── v1/routes/       # health.py, me.py, chat.py, admin.py, documents.py
│   │   ├── services/            # user, chat, admin, document, retrieval services
│   │   ├── repositories/        # user, conversation, message, document repos
│   │   ├── llm/
│   │   │   ├── base.py          # LLMProvider interface
│   │   │   ├── groq_provider.py
│   │   │   └── factory.py       # picks provider from settings
│   │   └── rag/
│   │       ├── embeddings/      # EmbeddingProvider interface, Pinecone impl, factory
│   │       ├── vectorstore/     # VectorStore interface, Pinecone impl, factory
│   │       ├── parsing.py       # PDF/DOCX/TXT/MD → pages of text
│   │       ├── chunking.py      # pages → overlapping chunks
│   │       └── storage.py       # original file storage under data/uploads
│   ├── alembic/ + alembic.ini
│   └── tests/                   # unit (service, repo) + API tests
├── frontend/
│   ├── app.py                   # Streamlit entry, login gate, navigation
│   ├── views/                   # chat.py, documents.py, admin.py
│   ├── services/api_client.py   # Typed HTTP client to backend, attaches bearer token
│   └── auth/                    # Entra sign-in helpers
├── docker/ (or Dockerfiles in each app folder)
├── docker-compose.yml
├── .env.example
├── pyproject.toml / uv.lock
└── README.md
```

### 5.3 Layering rules

- **api layer**: routes, Pydantic schemas, auth dependencies, HTTP status mapping. Calls
  services only. No SQLAlchemy imports, no LLM imports.
- **service layer**: business logic, orchestration, LLM calls via the `LLMProvider`
  interface. Calls repos. Raises app exceptions (e.g. `NotFoundError`,
  `ForbiddenError`), never `HTTPException`.
- **repo layer**: all database reads/writes via SQLAlchemy session. No business rules,
  no HTTP concepts. Returns ORM models or simple dataclasses.
- Wiring through FastAPI `Depends` so tests can override any layer.
- Exception handlers in `main.py` turn app exceptions into a consistent JSON error shape:
  `{"error": {"code": "...", "message": "...", "request_id": "..."}}`.

### 5.4 Authentication and authorisation

**Who can sign in**
- Any member account in the organisation's tenant **(user)**. "Assignment required" is left
  **off**; README notes it can be switched on later to restrict an app to assigned users.
- Guest (B2B) accounts in the tenant are rejected by the API **(my call)**: the
  registration adds the `acct` optional claim to the access token (0 = member, 1 = guest);
  the backend returns 403 when `acct` is 1, and fails closed (403, with a clear log line
  saying the optional claim is not configured) when the claim is missing.

**Entra setup (my call: one app registration)**
- One Entra app registration, single tenant ("Accounts in this organizational directory only").
- It exposes an API scope (e.g. `api://<client-id>/access_as_user`) and defines an App Role
  `Admin` (value `Admin`, allowed member type: Users/Groups).
- Streamlit acts as the confidential web client of the same registration (client secret,
  redirect URI to the Streamlit callback).
- README includes step-by-step portal instructions to create this, add the redirect URI,
  create the secret, define the scope and the Admin role, add the `acct` optional claim to
  the access token, set the access token version (builder picks v2 and validates matching
  `iss`/`aud`), and assign admins to the role.

**Frontend (Streamlit)**
- Unauthenticated users see only a "Sign in with Microsoft" screen.
- Sign-in uses the OAuth2 authorisation-code flow against the tenant authority and obtains
  an **access token for the API scope**. Mechanism is the builder's choice (see §7):
  Streamlit's native `st.login` OIDC support if it can provide the access token, otherwise
  MSAL for Python.
- Token is kept in Streamlit session state, refreshed or user re-prompted on expiry.
- `api_client` attaches `Authorization: Bearer <token>` to every backend call.
- Admin page appears in navigation only for users whose token has the `Admin` role — this
  is cosmetic; the backend enforces it.
- Sign-out clears session and signs out of Entra.

**Backend (FastAPI)**
- Every route except `/health` requires a valid bearer token.
- Validation: signature against the tenant's JWKS (cached, refreshed on unknown `kid`),
  `iss` matches the tenant, `aud` matches the API, `tid` equals the configured tenant,
  token not expired. Reject otherwise with 401. Then reject guests (`acct` ≠ 0) with 403.
- `get_current_user` dependency: validates the token, then upserts the user into the
  `users` table on each request (or first-seen per process — builder's call), and returns a
  `CurrentUser` (id, entra_oid, name, email, roles).
- `require_admin` dependency: 403 unless `Admin` is in the token's `roles` claim.
- Roles are always read from the token; there is no role column or admin table.

### 5.5 Data model (initial)

- `users`: id (PK), entra_oid (unique), email, display_name, created_at, last_seen_at
- `conversations`: id (PK), user_id (FK), title, knowledge_scope (`none`/`personal`/
  `company`, set at creation, never changed), created_at, updated_at
- `messages`: id (PK), conversation_id (FK), role (`user`/`assistant`/`system`), content,
  model, prompt_tokens, completion_tokens, sources (JSON, nullable: list of
  `{document_id, filename, page}`), created_at
- `documents`: id (PK), scope (`personal`/`company`), owner_user_id (FK, the uploader),
  filename, content_type, size_bytes, storage_path, status (`processing`/`ready`/`failed`),
  error_message (nullable), chunk_count, created_at, updated_at

SQLite file path from config, default `./data/app.db`. Alembic manages schema from the
first migration. SQLite foreign keys enabled via connection pragma.

### 5.6 LLM layer

- `LLMProvider` interface with at least:
  - `chat(messages, *, model=None, temperature=None, max_tokens=None) -> LLMResponse`
    (content, model, prompt_tokens, completion_tokens)
  - `stream_chat(...)` → async iterator of text chunks (plus final usage when available)
- `GroqProvider` implements it using the official `groq` SDK.
- `factory.get_llm_provider(settings)` returns the provider named by `LLM_PROVIDER`
  (default `groq`). Adding OpenAI/Azure OpenAI later = one new class + one factory entry.
- Settings: `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` (or provider-specific key),
  `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `LLM_TIMEOUT_SECONDS`.
- Provider errors (rate limit, timeout, auth) mapped to app exceptions → clean JSON errors
  and a friendly message in the UI. Groq free tier rate limits are expected; surface them
  clearly rather than retrying forever.

### 5.7 Sample features

These exist to prove the wiring and serve as copy-from examples.

**Chat**
- `POST /api/v1/conversations` — create, with `knowledge_scope` (`none` default,
  `personal`, `company`); see §5.13 for how scoped chats answer
- `GET /api/v1/conversations` — list current user's conversations
- `GET /api/v1/conversations/{id}/messages` — history (404 if not owner's)
- `POST /api/v1/conversations/{id}/messages` — send a user message, get assistant reply;
  streaming response supported (builder's choice of SSE vs chunked text — §7)
- Streamlit chat page: sidebar list of conversations, "new chat" (with a choice of
  "No documents" / "My documents" / "Company documents"), chat window with
  `st.chat_message` / `st.chat_input`, streamed reply, sources shown under document answers.

**Documents** — see §5.13.

**Me**
- `GET /api/v1/me` — current user profile and roles.

**Admin**
- `GET /api/v1/admin/users` — list users with conversation/message counts and last seen.
- Streamlit admin page showing that table.
- Non-admin gets 403 from the API; page hidden for them in the UI.

**Health**
- `GET /health` — unauthenticated liveness; checks DB reachable.

### 5.8 Logging (user: text-based)

- Python `logging`, plain-text format, e.g.
  `2026-10-24 10:57:01 | INFO | app.services.chat_service | req=ab12 user=jdoe@org | message`
- Handlers: console + rotating file (`TimedRotatingFileHandler`, daily, keep N days from config).
- Separate log files for backend and frontend, under `LOG_DIR` (default `./logs`).
- Backend middleware assigns a request ID (or accepts an incoming `X-Request-ID`), logs
  method, path, status, duration, user. Request ID returned in the response header and
  error body. Frontend sends a request ID with each call so lines can be correlated.
- LLM calls log provider, model, token counts, latency, success/failure — **not** prompt or
  response content (user).
- Tokens, secrets and Authorization headers are never logged.
- Document processing logs document id, scope, page/chunk counts, timings and failures —
  not document text. Embedding/vector calls log provider, counts and latency only.
- `LOG_LEVEL` from config.

### 5.9 Configuration

All settings via environment / `.env`, typed with pydantic-settings, validated at startup
(fail fast on missing required values). `.env.example` documents every key:
`ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET`, `ENTRA_API_SCOPE`,
`ENTRA_REDIRECT_URI`, `API_BASE_URL`, `DATABASE_URL`, `LLM_*`, `LOG_LEVEL`, `LOG_DIR`,
`LOG_RETENTION_DAYS`, `CORS_ORIGINS` (if needed), plus the RAG keys in §5.13.

### 5.10 Docker

- One Dockerfile per app (backend, frontend), slim Python 3.12 base, `uv` install,
  non-root user.
- `docker-compose.yml` with `backend` and `frontend` services; frontend reaches backend by
  service name; ports exposed for local use (e.g. 8000 API, 8501 Streamlit).
- Named volumes (or bind mounts) for `data/` (SQLite and `data/uploads/`) and `logs/`.
  Pinecone is a cloud service; no vector DB container.
- Backend runs Alembic migrations on startup before serving.
- Both apps also runnable without Docker (`uv run uvicorn ...`, `uv run streamlit run ...`);
  README documents both.

### 5.11 Testing and quality

- pytest. Tests run offline: Entra token validation overridden with a fake current user
  (normal and admin), LLM provider replaced with a fake provider, embeddings and vector
  store replaced with in-memory fakes (no Pinecone account needed to run tests).
- RAG tests cover: parsing each file type, chunking boundaries/overlap, upload validation
  (type, size, empty text), personal-document isolation between users (listing, delete,
  retrieval — the fake vector store honours filters so a missing owner filter fails the
  test), company upload/delete admin-only, document delete removes vectors, scoped chat
  answers include sources, low-score matches are dropped and the chat still answers with
  empty sources, API starts and plain chat works when the vector store is unavailable.
- Repo tests against a temporary SQLite database.
- Service tests with fake repos/provider.
- API tests with FastAPI `TestClient`, covering: 401 without token, 403 for non-admin on
  admin route, conversation ownership (404 for another user's conversation), chat happy path.
- Unit tests for token validation logic using locally generated keys/tokens (wrong tenant,
  wrong audience, expired, missing role, guest account, missing `acct` claim).
- Ruff lint + format config in `pyproject.toml`.

### 5.12 README

Quick start (Docker and local), Entra app registration walkthrough, `.env` reference,
"how to add a new feature" (route → schema → service → repo → migration, using chat as the
example), "how to add a new LLM provider", "how to switch from SQLite to Postgres",
Pinecone setup (account, API key, index created automatically), "how to add a vector store
or embedding provider", "how a new feature uses retrieval with a personal or company
collection".

### 5.13 Document Q&A (RAG)

**Collections (user: both, used by different features)**
- **Personal**: a user's own documents; only that user can list, delete or retrieve them.
- **Company**: shared org-wide; every signed-in user can list and retrieve; only Admins can
  upload or delete.
- A conversation is bound to exactly one source at creation (`knowledge_scope`), never a mix.
- Pinecone layout **(my call, sized for the free Starter tier, which caps namespaces per
  index)**: two namespaces per index, `personal` and `company`. Every personal vector carries
  `owner_oid` metadata, and every personal query is filtered by `owner_oid` = the
  authenticated user's Entra oid. The filter and namespace are set on the server inside
  `RetrievalService` / the vector store adapter from the authenticated user — never from
  client input — and no code path queries the `personal` namespace without the owner filter.
  Works the same on paid plans.

**Upload and processing**
- `POST /api/v1/documents` (multipart: `file`, `scope`) → 202 with the document record in
  status `processing`. `scope=company` requires Admin (403 otherwise).
- Validation before accepting: extension/type in PDF, DOCX, TXT, MD (415
  `unsupported_file_type`), size ≤ `MAX_UPLOAD_MB` (default 10; 413 `file_too_large`).
- Original file saved under `UPLOAD_DIR` (default `./data/uploads`) with a server-generated
  name; the user's filename is stored only as metadata.
- Processing runs in-process after the response (FastAPI background task) **(my call)**:
  parse to pages → chunk (`RAG_CHUNK_SIZE` 1000 chars, `RAG_CHUNK_OVERLAP` 150, never
  across pages) → embed (passage mode) in batches → upsert to the namespace.
- Vector ids `doc-<document_id>#<chunk_index>`; metadata: `document_id`, `owner_oid`,
  `filename`, `page` (omitted for DOCX/TXT/MD), `chunk_index`, `text`.
- Success → status `ready`, `chunk_count` set. Any failure (no extractable text, e.g. a
  scanned PDF → "No text found in this file (scanned PDFs are not supported)"; parse error;
  Pinecone/embedding error) → status `failed` with `error_message`; partial vectors removed.
- On backend startup, documents still `processing` are marked `failed` ("Processing was
  interrupted; please upload again").

**Listing and deletion**
- `GET /api/v1/documents?scope=personal|company` — personal: caller's own; company: all.
- `GET /api/v1/documents/{id}` — status; 404 if the caller can't see it.
- `DELETE /api/v1/documents/{id}` → 204. Personal: owner only; company: Admin only;
  otherwise 404 (personal) or 403 (company). Deletes vectors (by id prefix), the stored file,
  then the row.

**Retrieval and answering**
- `RetrievalService.search(user, scope, query, top_k) -> list[RetrievedChunk]` is the reusable
  entry point for future features; it resolves the namespace from `user` + `scope`.
- In a `personal`/`company` conversation, each new user message: embed it (query mode) →
  top `RAG_TOP_K` (default 5) chunks from that one namespace, keeping only matches with
  score ≥ `RAG_MIN_SCORE` **(my call)** (default 0.78 for e5 cosine scores; README says to
  tune it per model) → system prompt gains a
  context block of numbered excerpts and the instruction to answer only from them, cite
  `[n]`, and say it doesn't know when the excerpts don't cover the question → LLM call as in
  §5.6 (streaming supported) → assistant message saved with `sources` = deduplicated
  `{document_id, filename, page}` of all chunks that passed the threshold and were given to
  the model **(my call: not parsed from `[n]` citations)**. During a streamed reply the
  frontend shows sources after the stream ends by re-reading the saved message.
- If nothing passes the threshold (or there are no documents yet), the LLM is told no
  documents matched and answers accordingly; `sources` is empty.
- Conversation history (last `CHAT_HISTORY_LIMIT` messages) is still included; only the
  latest user message is used as the search query **(my call)**.

**Interfaces**
- `EmbeddingProvider`: `embed_documents(texts) -> list[vector]`, `embed_query(text) -> vector`,
  `dimension`. Default `PineconeEmbeddingProvider` (Pinecone Inference,
  `multilingual-e5-large`, input_type passage/query, batches within the model's limit).
- `VectorStore`: `ensure_index()`, `upsert(namespace, records)`, `query(namespace, vector,
  top_k, filter) -> matches`, `delete_by_prefix(namespace, prefix)`. Default
  `PineconeVectorStore` (serverless index, cosine metric, dimension from the embedding
  provider).

**Startup and availability (my call)**
- Pinecone settings are required (document Q&A is part of the base), but the API does
  **not** depend on Pinecone to start: at startup it tries `ensure_index()` (creating the
  index if missing) and only logs an error on failure; the adapter retries `ensure_index`
  on first use. Sign-in, plain chat and history keep working when Pinecone is down;
  document routes and scoped chats return 502 `vector_store_unavailable`.
- `/health` adds `"vector_store": "ok" | "error"` but stays 200 when only the vector store
  is down (it still returns 503 when the database is down).
- README has a short "removing document Q&A from an app" section listing what to delete.
- Embedding/vector errors map to app exceptions (`vector_store_unavailable`, 502) → clean
  JSON errors and a friendly UI message.

**Configuration**
`VECTOR_STORE_PROVIDER` (`pinecone`), `EMBEDDING_PROVIDER` (`pinecone`), `PINECONE_API_KEY`,
`PINECONE_INDEX_NAME` (default `genai-boilerplate`; README: use one index per app copied
from the boilerplate, and note the free tier's index-per-project limit), `PINECONE_CLOUD` (`aws`), `PINECONE_REGION` (`us-east-1`),
`EMBEDDING_MODEL` (`multilingual-e5-large`), `EMBEDDING_DIMENSION` (1024), `RAG_TOP_K`,
`RAG_MIN_SCORE`,
`RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP`, `MAX_UPLOAD_MB`, `UPLOAD_DIR`.

**Frontend**
- Documents page with tabs "My documents" and "Company documents": file uploader (allowed
  types, size limit shown), table of filename / status / chunks / uploaded, refresh button
  to update `processing` rows, delete with confirmation. The company tab shows upload and
  delete only to Admins.
- Chat: "New chat" asks which source to use; the conversation list shows each chat's
  source; document answers show a "Sources" list (filename, page) under the reply.

## 6. Constraints

- Developers are on Windows; local (non-Docker) setup must work on Windows.
- Groq free tier: rate limits and model availability can change; model name is config.
- Deployment target undecided: nothing host-specific baked in; the app must read all
  config from environment and write only to `data/` and `logs/`.
- SQLite is single-writer; acceptable for the boilerplate. Not designed for multiple backend
  replicas (also true of in-process document processing and local file storage).
- Pinecone free (Starter) tier: limited storage, one cloud region, rate limits on hosted
  inference; the backend needs internet access to Pinecone, tests do not.

## 7. Left to the builder

- Streamlit sign-in mechanism: native `st.login` vs MSAL — whichever can reliably obtain an
  access token for the API scope with the installed Streamlit version.
- Streaming transport for chat replies (SSE vs plain chunked response).
- One `pyproject.toml` with groups vs one per app.
- Sync vs async SQLAlchemy (async preferred if it stays simple with SQLite/aiosqlite).
- Whether user upsert happens every request or is cached per process.
- Exact Docker base image tags and pinned library versions (pin to current stable releases).
