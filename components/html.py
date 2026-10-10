"""Render provided HTML pages/fragments with live data via Jinja2 templates.

Workflow for each HTML page you receive:
  1. Save it under templates/ (split into fragments if parts need widgets).
  2. Replace hard-coded values with Jinja placeholders: {{ user.name }},
     {% for row in orders %}...{% endfor %}.
  3. In the view, fetch data from `services.data` and call render_template().
"""
from __future__ import annotations

from typing import Any

import streamlit as st
from jinja2 import Environment, FileSystemLoader, select_autoescape

from config.settings import get_settings

from .icons import image, svg


@st.cache_resource
def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(get_settings().templates_dir),
        autoescape=select_autoescape(["html", "htm"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["icon"] = svg
    env.globals["image"] = image
    return env


def render_string(template_name: str, **context: Any) -> str:
    return _env().get_template(template_name).render(**context)


def render_template(
    template_name: str,
    *,
    scripts: bool = False,
    height: int | None = None,
    **context: Any,
) -> None:
    """Render a template into the page.

    scripts=False -> st.html: inherits page width, CSS works, JS is stripped.
    scripts=True  -> sandboxed iframe: JS works; set `height` (px).
    """
    html = render_string(template_name, **context)
    if scripts:
        st.iframe(html, height=height or 600)
    else:
        st.html(html)
