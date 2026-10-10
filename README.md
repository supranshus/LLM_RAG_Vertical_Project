# Project Management System – Streamlit

A Streamlit version of the provided HTML pages:

1. **Create project** (`views/create_project.py`, from `create-project.html`): the form that feeds the generator.
2. **Generated documents** (`views/generated_documents.py`, from `generated-documents.html`): problem statement,
   project description, sprint plan, task breakdown and test cases.

**Generate sprints** saves the project, runs generation, and opens page 2 (`?project_id=...`).
**Back to project setup** returns to the form with its values kept. **Export all** downloads the documents as a zip of
Markdown files.

It runs on mock data for now. Switching to the real backend is a config change.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # optional, defaults to mock data
streamlit run app.py
python -m pytest              # tests
```

## Project structure

```
app.py                     Entry point + page registry (st.navigation)
views/                     One script per page
templates/<page>/          Jinja2 HTML fragments taken from the provided pages
assets/css/theme.css       Shared design tokens + Streamlit overrides
assets/css/<page>.css      Page styles (from the provided HTML)
.streamlit/config.toml     Theme colors and fonts from the designs
components/
  html.py                  render_template(): renders a template with data
  icons.py                 SVG icons from the designs
  ui.py                    load_css(), inject_css(), icon_rule()
  documents.py             Generated-docs formatting + Markdown export
  state.py                 Keeps form values when switching pages
services/
  projects.py              Project/document API calls used by the pages
  __init__.py              Generic cached `data` service
  endpoints.py             Resource name -> API path + mock file
  mock_provider.py         Serves mock_data/*.json (writes kept in memory)
  api_provider.py          HTTP client (requests, bearer token, multipart)
config/settings.py         Settings from env / .env / st.secrets
mock_data/                 Mock API responses
```

## Data flow and API contract

```
view  ->  services.projects  ->  services.data  ->  MockProvider | ApiProvider
```

| Action                   | Method & path                       | Mock                          |
|--------------------------|-------------------------------------|-------------------------------|
| Save draft / create      | `POST /projects`                    | in-memory store               |
| Save again               | `PATCH /projects/{id}`              | in-memory store               |
| Upload BRD               | `POST /projects/{id}/brd` (multipart, field `file`) | echoes the file name |
| Generate                 | `POST /projects/{id}/generate`      | `generated_documents.json`    |
| Load generated documents | `GET /projects/{id}/documents`      | `generated_documents.json`    |
| Project name for header  | `GET /projects/{id}`                | in-memory store               |

- The request body for `POST /projects` is built by `build_payload()` in `views/create_project.py`.
- The documents response shape is `mock_data/generated_documents.json`. Documents are structured data (sections,
  sprints, tasks, test cases), not HTML, so the page renders whatever the API returns. Text documents may include a
  `word_count`. If it's missing, the page counts the words itself.

## Switching to the real API

1. Set `DATA_SOURCE=api`, `API_BASE_URL` and `API_TOKEN` in `.env` (or `.streamlit/secrets.toml`).
2. Adjust the paths in `services/endpoints.py` if the backend uses different routes. If responses are wrapped
   (for example `{"data": ...}`), set `data_key="data"`.
3. Keep the mock JSON in the same shape as the real responses. The pages need no changes.

## How the HTML designs were ported

- Static markup (sidebar, headers, document cards) is rendered from Jinja templates with `st.html`, using the CSS
  from the original pages.
- Interactive parts (inputs, toggle, buttons, upload, document switcher) are native Streamlit widgets. CSS targets
  each one through the `st-key-<key>` class Streamlit adds to keyed widgets and containers.
- `st.html` strips `<svg>`, so icons are drawn as CSS masks (`components/icons.py`). They still take the text color.
- The section highlight in the Create project sidebar is the one piece of JavaScript
  (`templates/create_project/scroll_spy.html`).

## Adding a page

1. Save its markup as fragments in `templates/<page>/` and its CSS in `assets/css/<page>.css`.
2. Register its API resources in `services/endpoints.py`, add mock JSON to `mock_data/`, and add service functions.
3. Create `views/<page>.py` and register it in `app.py`.
