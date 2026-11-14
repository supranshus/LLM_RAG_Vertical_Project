# AI Powered Project Management Platform

Starter project for GenAI apps. Copy it, fill in `.env`, and build on top.

- **Frontend:** Streamlit
- **Backend:** FastAPI + SQLite
- **LLM:** Groq
- **Document Q&A:** Pinecone
- **Sign-in:** Microsoft Entra ID, with an Admin role

It comes with sign-in, chat with history, document upload and Q&A, and an admin page.

## What you need

- A Microsoft Entra app registration (steps below)
- A [Groq API key](https://console.groq.com/keys)
- A [Pinecone API key](https://app.pinecone.io)
- Docker, **or** [uv](https://docs.astral.sh/uv/) (setup steps below)

## Setup

Copy the example env file and fill in the empty values:

```bash
cp .env.example .env
```

Each key in `.env.example` has a comment explaining it. The app won't start if a required
value is missing.

Also replace `<client-id>` in `ENTRA_API_SCOPE` with your real client ID. It isn't empty, so
it's easy to miss.

Keep each value on its own line. If you delete the comments, make sure no comment text is
left at the end of a value.

## Run with Docker

```bash
docker compose up --build
```

- App: http://localhost:8501
- API docs: http://localhost:8000/docs

## Run without Docker

### Install uv

uv is the tool we use to manage Python and the project's packages.

**Windows** (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux**:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen your terminal, then check that it works:

```bash
uv --version
```

You don't need to install Python yourself. On the first `uv sync`, uv downloads Python 3.12
and creates a `.venv` folder inside `backend/` and `frontend/` with all the packages.

### Start the app

Open two terminals.

**Backend**

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

**Frontend**

```bash
cd frontend
uv sync
uv run streamlit run app.py
```

Then open http://localhost:8501.

## Entra app registration

In the [Azure portal](https://portal.azure.com), go to **Microsoft Entra ID → App
registrations → New registration**:

1. Pick **single tenant** and set the redirect URI to **Web**, `http://localhost:8501`.
2. Copy the client ID and tenant ID into `ENTRA_CLIENT_ID` and `ENTRA_TENANT_ID`.
3. **Certificates & secrets:** create a client secret and put its value in `ENTRA_CLIENT_SECRET`.
4. **Expose an API:** keep the default `api://<client-id>` and add a scope called
   `access_as_user`. Set `ENTRA_API_SCOPE=api://<client-id>/access_as_user`.
5. **Manifest:** set `requestedAccessTokenVersion` to `2`.
6. **Token configuration:** add the optional claim `acct` to the **Access** token.
7. **App roles:** create a role with value `Admin`, then assign it to your admins under
   **Enterprise applications → your app → Users and groups**.

If sign-in shows **"Need admin approval"**, your organisation doesn't let users consent to apps.
Ask an Entra admin to go to **API permissions → Add a permission → My APIs**, add
`access_as_user`, and click **Grant admin consent**.

## Tests

Run these from the project root:

```bash
cd backend
uv run pytest
cd ../frontend
uv run pytest
```

Tests run offline, and you don't need real keys. They still read `.env`, though, so a broken
value in it will fail the tests.

## Notes

- Use a different `PINECONE_INDEX_NAME` for each app you build from this. The index is
  created automatically on first start.
- Logs: when running locally, they go to `backend/logs/backend.log` and
  `frontend/logs/frontend.log`. With Docker, they're in the `app-logs` volume
  (`docker compose logs -f` shows them too).
- Project structure: `backend/app` has routes in `api/`, logic in `services/`, and database
  code in `repositories/`. The frontend pages are in `frontend/views/`.
