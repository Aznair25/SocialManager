"""Turning deck copy into safe HTML.

Order matters: escape first, then convert `**word**` into an accent span. Doing
it the other way round would let deck copy inject markup.
"""
import html

from ..domain.text import HIGHLIGHT_RE


def escape(value) -> str:
    return html.escape(str(value), quote=True)


def rich_text(value) -> str:
    """Escape, then `**word**` -> accent span."""
    return HIGHLIGHT_RE.sub(r'<span class="hl">\1</span>', escape(value))


def document(head: str, css: str, body: str) -> str:
    """A standalone page. Everything is inlined — these are fed to `set_content()`,
    which has no origin to resolve external files against."""
    return ('<!doctype html><html><head><meta charset="utf-8">%s'
            "<style>%s</style></head><body>%s</body></html>" % (head, css, body))
