"""Keep form values alive when the user navigates to another page and back.

Streamlit drops a widget's value from session_state when the widget is not
rendered in a run. Re-assigning the key turns it into plain session state,
which survives until the widget is shown again.
"""
from __future__ import annotations

import streamlit as st

# File uploaders and buttons can't be assigned through session_state.
_NOT_ASSIGNABLE = {"cp_brd", "cp_employee_excel"}


def persist_form_state(prefix: str = "cp_") -> None:
    for key in list(st.session_state.keys()):
        if isinstance(key, str) and key.startswith(prefix) and key not in _NOT_ASSIGNABLE:
            st.session_state[key] = st.session_state[key]
