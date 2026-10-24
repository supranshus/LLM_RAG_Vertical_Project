"""SVG icons from the provided designs.

st.html strips inline <svg>, so icons are drawn as a CSS mask over a <span>
whose background is currentColor — they still take the surrounding text color.
"""
from __future__ import annotations

from urllib.parse import quote

from markupsafe import Markup, escape

from config.settings import get_settings

_ATTRS = 'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"'

_PATHS = {
    "pin": '<path d="M12 21s7-7.2 7-12a7 7 0 10-14 0c0 4.8 7 12 7 12z"/><circle cx="12" cy="9" r="2.4"/>',
    "pin-sm": '<path d="M12 21s7-7.2 7-12a7 7 0 10-14 0c0 4.8 7 12 7 12z"/><circle cx="12" cy="9" r="2.2"/>',
    "upload": '<path d="M12 15V4"/><path d="M7.5 8.5L12 4l4.5 4.5"/><path d="M4 15v3a2 2 0 002 2h12a2 2 0 002-2v-3"/>',
    "download": '<path d="M12 4v11"/><path d="M7.5 11.5L12 16l4.5-4.5"/><path d="M4 20h16"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "check": '<path d="M20 6L9 17l-5-5"/>',
    "alert": '<circle cx="12" cy="12" r="9"/><line x1="12" y1="7.5" x2="12" y2="13"/>'
             '<circle cx="12" cy="16.3" r="0.6" fill="currentColor" stroke="none"/>',
    "file-text": '<path d="M7 3h7l5 5v12a1 1 0 01-1 1H7a1 1 0 01-1-1V4a1 1 0 011-1z"/><path d="M14 3v5h5"/>'
                 '<line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/>',
    "file": '<path d="M7 3h7l5 5v12a1 1 0 01-1 1H7a1 1 0 01-1-1V4a1 1 0 011-1z"/><path d="M14 3v5h5"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/>'
                '<line x1="8" y1="3" x2="8" y2="7"/><line x1="16" y1="3" x2="16" y2="7"/>',
    "calendar-sm": '<rect x="3" y="5" width="18" height="16" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/>',
    "checklist": '<path d="M9 6h11"/><path d="M9 12h11"/><path d="M9 18h11"/><path d="M4 6l1.2 1.2L7 5.4"/>'
                 '<path d="M4 12l1.2 1.2L7 11.4"/><path d="M4 18l1.2 1.2L7 17.4"/>',
    "checklist-sm": '<path d="M9 6h11"/><path d="M9 12h11"/><path d="M9 18h11"/><path d="M4 6l1.2 1.2L7 5.4"/>',
    "shield": '<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z"/><path d="M9 12l2 2 4-4"/>',
    # Workspace navigation and status icons.
    "gauge": '<path d="M4 18a8 8 0 1116 0"/><path d="M12 14l4-3.5"/><circle cx="12" cy="14" r="1.3"/>',
    "board": '<rect x="3" y="4" width="18" height="16" rx="2"/><line x1="9" y1="4" x2="9" y2="20"/>'
             '<line x1="15" y1="4" x2="15" y2="20"/>',
    "tasks": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8.5 12l2.2 2.2L15.5 9.5"/>',
    "chat": '<path d="M20 15a2 2 0 01-2 2H8l-4 3V6a2 2 0 012-2h12a2 2 0 012 2z"/>',
    "bell": '<path d="M18 9a6 6 0 10-12 0c0 5-2.2 6.5-2.2 6.5h16.4S18 14 18 9z"/>'
            '<path d="M13.7 19a2 2 0 01-3.4 0"/>',
    "layers": '<path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 13l9 5 9-5"/>',
    "users": '<path d="M16 19v-1.5a3.5 3.5 0 00-3.5-3.5h-5A3.5 3.5 0 004 17.5V19"/>'
             '<circle cx="10" cy="8" r="3.2"/><path d="M20 19v-1.5a3.5 3.5 0 00-2.6-3.4"/>'
             '<path d="M15.5 5a3.2 3.2 0 010 6.2"/>',
    "flag": '<path d="M5 21V4"/><path d="M5 5h10l-1.6 3.2L15 11.5H5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5V12l3 1.8"/>',
    "trend": '<path d="M4 16l5-5 3.5 3.5L20 7"/><path d="M15 7h5v5"/>',
    "send": '<path d="M20 4L10.5 13.5"/><path d="M20 4l-6.2 16-3.3-6.5L4 10.2 20 4z"/>',
    "sparkle": '<path d="M12 4l1.7 4.6L18 10l-4.3 1.4L12 16l-1.7-4.6L6 10l4.3-1.4L12 4z"/>'
               '<path d="M18.5 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7.7-1.8z"/>',
    "arrow-right": '<path d="M5 12h13"/><path d="M13 6.5L18.5 12 13 17.5"/>',
}


def css_url(name: str, stroke_width: float = 1.75) -> str:
    """The icon as a CSS url(), for use as a mask."""
    markup = f'<svg xmlns="http://www.w3.org/2000/svg" {_ATTRS} stroke-width="{stroke_width}">{_PATHS[name]}</svg>'
    return f'url("data:image/svg+xml,{quote(markup)}")'


def svg(name: str, stroke_width: float = 1.75, cls: str = "", size: int | None = None) -> Markup:
    """Icon markup for templates: {{ icon("pin") }}. Size it with CSS or ``size``."""
    url = css_url(name, stroke_width)
    style = f"-webkit-mask: {url} center / contain no-repeat; mask: {url} center / contain no-repeat;"
    if size:
        style += f" width: {size}px; height: {size}px;"
    return Markup(f'<span class="svg-icon {cls}" style="{escape(style)}"></span>')


def image(path: str, cls: str = "", alt: str = "") -> Markup:
    """An SVG file from assets/ as an <img> (keeps its own colors)."""
    markup = (get_settings().assets_dir / path).read_text(encoding="utf-8")
    src = f"data:image/svg+xml,{quote(markup)}"
    return Markup(f'<img class="{escape(cls)}" src="{src}" alt="{escape(alt)}">')
