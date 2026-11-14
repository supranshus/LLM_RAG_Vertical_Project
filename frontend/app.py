"""Entry point: `streamlit run app.py`.

Register every page here. Each page is a script in views/.
"""
import streamlit as st

from components.state import persist_form_state

st.set_page_config(page_title="Project Management System", page_icon="📍", layout="wide")

PAGES = [
    st.Page("views/projects.py", title="Projects", url_path="projects", default=True),
    st.Page("views/dashboard.py", title="Dashboard", url_path="dashboard"),
    st.Page("views/sprint_board.py", title="Sprint board", url_path="sprint-board"),
    st.Page("views/my_tasks.py", title="My tasks", url_path="my-tasks"),
    st.Page("views/assistant.py", title="Assistant", url_path="assistant"),
    st.Page("views/notifications.py", title="Notifications", url_path="notifications"),
    st.Page("views/create_project.py", title="Create project", url_path="create-project"),
    st.Page("views/generated_documents.py", title="Generated documents", url_path="generated-documents"),
]

persist_form_state()
st.navigation(PAGES, position="hidden").run()
