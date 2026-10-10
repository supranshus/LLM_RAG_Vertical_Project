"""Small helpers for styling native Streamlit widgets to match the designs.

Streamlit adds a ``st-key-<key>`` class to every keyed widget/container, so
per-widget CSS targets that class.
"""
from __future__ import annotations

import streamlit as st

from config.settings import get_settings

from .icons import css_url


def load_css(*files: str) -> None:
    """Inject CSS files from assets/css/."""
    css_dir = get_settings().assets_dir / "css"
    inject_css("\n".join((css_dir / f).read_text(encoding="utf-8") for f in files))


def inject_css(css: str) -> None:
    st.html(f"<style>{css}</style>")


def icon_rule(
    selector: str,
    icon: str,
    *,
    size: int = 16,
    color: str = "currentColor",
    stroke_width: float = 1.75,
    pseudo: str = "before",
) -> str:
    """CSS that draws an SVG icon as a ::before/::after of ``selector``."""
    return (
        f"{selector}::{pseudo} {{ content: ''; width: {size}px; height: {size}px; flex-shrink: 0;"
        f" background-color: {color};"
        f" -webkit-mask: {css_url(icon, stroke_width)} center / contain no-repeat;"
        f" mask: {css_url(icon, stroke_width)} center / contain no-repeat; }}"
    )
