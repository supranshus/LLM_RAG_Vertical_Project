# Project Management System – Streamlit

The whole front end, running on mock data. Switching to the real backend is a config change.

**Feature 1 — Create new project**

1. **Projects** (`views/projects.py`): the portfolio. Every project a person can see, with progress
   and risk worked out from its own tasks. This is the page the app opens on.
2. **Create project** (`views/create_project.py`, from `create-project.html`): the form that feeds the generator.

**Feature 2 — Generated documents**

3. **Generated documents** (`views/generated_documents.py`, from `generated-documents.html`): problem statement,
   project description, sprint plan, task breakdown and test cases.

**Feature 3 — Daily progress**

4. **Dashboard** (`views/dashboard.py`): progress, sprint-by-sprint completion, what needs attention,
   team workload and recent activity for the current project (FR-009, FR-011).
5. **Sprint board** (`views/sprint_board.py`): every task in the sprint grouped by status, with filters.
   Pick a task underneath the board to open it and post an update.
6. **My tasks** (`views/my_tasks.py`): what is assigned to the signed-in person, and the day's update (FR-008).
7. **Assistant** (`views/assistant.py`): report progress or ask about status in plain language
   (FR-007, FR-008, FR-009).

**Feature 4 — Notifications & alerts**

8. **Notifications** (`views/notifications.py`): risk alerts and notifications, with acknowledge,
   resolve and dismiss, plus a risk check that shows what the detector sees right now
   (FR-010, FR-012).

**Generate sprints** saves the project and runs generation, then stays on the
full-page generation preview. The redirect to generated documents is temporarily
commented out. The status card uses the existing green theme to show project
collection, BRD availability, and the task/sprint/document workflow, and remains
visible on reruns without repeating generation. The current API returns all
generation stages together; the preview does not simulate per-stage completion.
If saving or generation fails, the form returns with an error so you can retry.
**Back to project setup** returns to the form with its values kept. **Export all** downloads the documents as a zip of
Markdown files.

## The app shell

Every workspace page (1, 4–8) opens with `components/shell.py`, which draws the dark rail: brand,
project picker, navigation, the signed-in person and a **Viewing as** switcher.

There is no authentication in this phase, so the signed-in person is a session value. Changing it
with **Viewing as** is how the role-based views are demonstrated (FR-011): a director and a project
manager see every project, a tech lead and a team member see only the projects they are on. The rule
lives in `services/workspace.visible_projects()` — in the service layer, not the page — so it still
holds when these calls move to the real backend.

## Where the numbers come from

Every figure on every screen is computed in `components/metrics.py` from the task rows: percent
complete, overdue, blocked, burn rate, project health and the risk flags. Nothing is hard-coded and
nothing is produced by a model, which is why the dashboard, the board and the assistant always report
the same number. The assistant only phrases what the metrics module worked out.

`components/assistant.py` is a stand-in for the real conversational assistant. It keeps the intended
shape — classify the message into an intent, then route it to a handler — but uses keyword rules
instead of a model call. Replace `classify`, `extract_update` and the phrasing in `answer_status`
with the Groq calls and the pages do not change.

When the backend exposes a metrics endpoint, the functions in `components/metrics.py` are replaced by
fields in its response.

## BRD Upload

The optional BRD upload accepts PDF, DOCX, and UTF-8 TXT documents up to 50 MB.
Empty files, unsupported extensions, and files that fail basic format checks
(PDF header, DOCX package entries, or UTF-8 text) show an error directly below
the uploader. Saving a draft and generating sprints are blocked until the
invalid file is removed or replaced. These checks are not a full document
parser or malware scanner.

## Employee Excel Import

The Team section accepts `.xlsx` workbooks and adds imported employees to the
available employee list. Select an employee and use **Add member** to include
them in the project. Imports remain available for the current session.

The first worksheet must have a header row with `name`. Optional columns are
`id`, `role`, `experience_years`, and `skills` (comma-separated). Column names
are case-insensitive; spaces may replace underscores. Experience must be a
non-negative number. Files are limited to 5 MB and 5,000 employee rows.
Invalid rows reject the import without adding any records. Reimporting the
same employee ID updates its imported record instead of adding a duplicate;
without an ID, name and role identify the imported employee. Imported IDs are
separate from API employee IDs. Install `openpyxl` via the project requirements
to enable workbook parsing.

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
  html.py                  render_template(), text_blocks(), the `rich` filter
  icons.py                 SVG icons from the designs
  ui.py                    load_css(), inject_css(), icon_rule()
  documents.py             Generated-docs formatting + Markdown export
  state.py                 Keeps form values when switching pages
  shell.py                 The rail, role switcher and page context
  metrics.py               Progress, risk and workload computed from task rows
  tasks.py                 Task rows -> what the task templates expect
  task_panel.py            Task detail + "post an update" composer
  assistant.py             Keyword stand-in for the conversational assistant
services/
  projects.py              Project/document API calls used by the pages
  workspace.py             People, sprints, tasks, updates and notifications
  __init__.py              Generic cached `data` service
  endpoints.py             Resource name -> API path + mock file
  mock_provider.py         Serves mock_data/*.json (writes kept in memory)
  api_provider.py          HTTP client (requests, bearer token, multipart)
config/settings.py         Settings from env / .env / st.secrets
mock_data/                 Mock API responses
```

Styles are concatenated into one `<style>` block, so **a literal `<` anywhere in a CSS file** — a
comment included — would make the sanitiser behind `st.html` drop the whole stylesheet with no
error. `inject_css()` escapes it, and a test keeps the CSS files clean.

## Data flow and API contract

```
view  ->  services.projects  ->  services.data  ->  MockProvider | ApiProvider
```

| Action                   | Method & path                       | Mock                          |
|--------------------------|-------------------------------------|-------------------------------|
| Load available employees | `GET /employees`                    | `mock_data/employees.json`    |
| Save draft / create      | `POST /projects`                    | in-memory store               |
| Save again               | `PATCH /projects/{id}`              | in-memory store               |
| Upload BRD               | `POST /projects/{id}/brd` (multipart, field `file`) | echoes the file name |
| Generate                 | `POST /projects/{id}/generate`      | `generated_documents.json`    |
| Load generated documents | `GET /projects/{id}/documents`      | `generated_documents.json`    |
| Project name for header  | `GET /projects/{id}`                | in-memory store               |

Workspace resources, through `services/workspace.py`:

| Action                      | Method & path                             | Mock                           |
|-----------------------------|-------------------------------------------|--------------------------------|
| People, roles, designations | `GET /users`                               | `mock_data/users.json`         |
| Skills and proficiency      | `GET /skills`, `GET /user-skills`          | `skills.json`, `user_skills.json` |
| Who is on a project         | `GET /project-members?project_id=…`        | `project_members.json`         |
| Sprint settings             | `GET /project-sprint-settings`             | `project_sprint_settings.json` |
| Deliverables (epics)        | `GET /deliverables?project_id=…`           | `project_deliverables.json`    |
| Sprints                     | `GET /sprints?project_id=…`                | `sprints.json`                 |
| Tasks                       | `GET /tasks?project_id=…`                  | `tasks.json`                   |
| Move a task                 | `PATCH /tasks/{task_id}`                   | in-memory store                |
| Progress notes              | `GET /task-updates`, `POST /task-updates`  | `task_updates.json`            |
| Alerts for a person         | `GET /notifications?recipient_user_id=…`   | `notifications.json`           |
| Acknowledge / resolve       | `PATCH /notifications/{id}`                | in-memory store                |

- The request body for `POST /projects` is built by `build_payload()` in `views/create_project.py`.
- The documents response shape is `mock_data/generated_documents.json`. Documents are structured data (sections,
  sprints, tasks, test cases), not HTML, so the page renders whatever the API returns. Text documents may include a
  `word_count`. If it's missing, the page counts the words itself.
- Names are joined in `services/workspace.py` (assignee, author, project), not stored on each row.

## Schema gaps and assumptions

Worth settling with the backend before the API is built:

1. **No table for progress notes.** The schema has no home for the daily updates FR-008 asks for, so
   the front end uses a `task_updates` resource: `task_id`, `project_id`, `author_id`, `note`,
   `status_after`, `progress_percentage`, `hours_logged`, `source` (`chat` or `form`), `created_at`.
   Either add that table or the Assistant and the activity feed have nowhere to write.
2. **`area` on a task is denormalised for display.** The schema reaches an area through
   `required_skill_id`; the mock also carries an `area` string ("Frontend", "Backend", "QA",
   "Design", "PM") because the tag on every card needs it. The backend should return it, or return
   the skill expanded.
3. **Fixed dates in the mock.** `mock_data` is anchored to sprint 3 of the Fleet project running
   12–23 Oct 2026, which is what makes the overdue and behind-schedule states show up. The pages
   compute against the real current date, so a demo well after that date shows the project further
   behind. Shift the dates in `sprints.json`, `tasks.json` and `projects.json` to re-centre it.
4. **Progress ignores the backlog.** `metrics.percent_complete()` counts only scheduled tasks, so
   adding backlog items does not make a project look less complete.
5. **A project with no tasks** reads as "Not started" rather than 0% complete.

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
4. For a workspace page, open it with `render_shell("<nav key>", page_css="<page>.css")` and add the
   key to `NAV` in `components/shell.py`. Write into `shell.main`.

The app's landing page is **Projects**, set by `default=True` in `app.py`. Move `default=True` back
to `views/create_project.py` to land on the form instead; the tests open Create project explicitly
through `_create_project_app()`, so they pass either way.
