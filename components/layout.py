"""Shared page helpers: error handling around data loading."""
from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import streamlit as st

from services import DataProviderError

T = TypeVar("T")


def safe_load(loader: Callable[[], T], message: str = "Loading...") -> T | None:
    """Run a data loader with a spinner; show a friendly error instead of a traceback."""
    try:
        with st.spinner(message):
            return loader()
    except DataProviderError as exc:
        st.error(f"Could not load data: {exc}")
        return None
