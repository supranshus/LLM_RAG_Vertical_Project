"""Render provided HTML pages/fragments with live data via Jinja2 templates.

Workflow for each HTML page you receive:
  1. Save it under templates/ (split into fragments if parts need widgets).
  2. Replace hard-coded values with Jinja placeholders: {{ user.name }},
     {% for row in orders %}...{% endfor %}.
  3. In the view, fetch data from `services.data` and call render_template().
"""
from __future__ import annotations

import re
from typing import Any

import streamlit as st
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from config.settings import get_settings

from .icons import image, svg

_BOLD = re.compile(r"\*\*(.+?)\*\*")


def rich(text: str) -> Markup:
    """Escape a line of text, then turn ``**bold**`` into ``<strong>``.

    Escaping first means the markup can only ever come from the asterisks, not
    from the text itself. Used for assistant replies.
    """
    return Markup(_BOLD.sub(r"<strong>\1</strong>", str(escape(text))))


def text_blocks(text: str) -> list[dict[str, Any]]:
    """Split plain text into paragraphs and bullet lists.

    Lines starting with "- " or "* " become one list; everything else is a
    paragraph. Used for task descriptions and assistant replies, both of which
    arrive as plain text with simple bullets.
    """
    blocks: list[dict[str, Any]] = []
    for line in [ln.strip() for ln in (text or "").split("\n") if ln.strip()]:
        if line.startswith(("- ", "* ")):
            if not blocks or blocks[-1]["type"] != "list":
                blocks.append({"type": "list", "items": []})
            blocks[-1]["items"].append(line[2:].strip())
        else:
            blocks.append({"type": "paragraph", "text": line})
    return blocks


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
    env.filters["rich"] = rich
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
