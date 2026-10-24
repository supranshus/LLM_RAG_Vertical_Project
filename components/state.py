"""Keep form values alive when the user navigates to another page and back.

Streamlit drops a widget's value from session_state when the widget is not
rendered in a run. Re-assigning the key turns it into plain session state,
which survives until the widget is shown again.
"""
from __future__ import annotations

import streamlit as st

# File uploaders and buttons can't be assigned through session_state.
_NOT_ASSIGNABLE = {"cp_brd", "cp_employee_excel"}
# cp_: the create-project form. app_: the shell (signed-in user, current project).
_PREFIXES = ("cp_", "app_")


def persist_form_state(prefixes: tuple[str, ...] = _PREFIXES) -> None:
    for key in list(st.session_state.keys()):
        if isinstance(key, str) and key.startswith(prefixes) and key not in _NOT_ASSIGNABLE:
            st.session_state[key] = st.session_state[key]
