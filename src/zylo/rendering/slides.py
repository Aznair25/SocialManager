"""One slide -> one standalone HTML document.

Templates are `{{placeholder}}` files. Every placeholder a template could want is
supplied for every role, because a missing key renders as empty and that is the
behaviour we want — a cover has no `body`, and the cover template simply never
asks for one.
"""
import re

from ..domain.deck import Deck, Slide
from ..domain.text import visible_length
from .assets import FontResolver
from .markup import document, escape, rich_text
from .templates import TemplateRepository
from .theme import CssVariableBuilder, Theme

PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


class SlideHtmlBuilder:
    def __init__(self, theme: Theme, templates: TemplateRepository,
                 fonts: FontResolver, css: CssVariableBuilder | None = None):
        self._theme = theme
        self._templates = templates
        self._fonts = fonts
        self._css = css or CssVariableBuilder(theme)

    def build(self, deck: Deck, slide: Slide, index: int, total: int) -> str:
        """`index` is 0-based; the slide counter it renders is 1-based."""
        values = self._values(deck, slide, index, total)
        filled = PLACEHOLDER_RE.sub(
            lambda m: values.get(m.group(1), ""),
            self._templates.slide_template(slide.role),
        )
        return document(
            head=self._fonts.head_html(),
            css="%s\n%s" % (self._css.build(deck.palette), self._templates.base_css()),
            body=filled,
        )

    def _values(self, deck: Deck, slide: Slide, index: int, total: int) -> dict:
        identity = self._theme.identity
        return {
            "paletteClass": deck.palette,
            "wordmark": escape(identity["wordmark"]),
            "handle": escape(identity["handle"]),
            "site": escape(identity["site"]),
            "email": escape(identity["email"]),
            "index": "%02d/%02d" % (index + 1, total),
            "kicker": escape(slide.raw("kicker", "")),
            "hook": rich_text(slide.raw("hook", "")),
            "value": rich_text(slide.raw("value", "")),
            # The template scales the numeral by how many characters it has to fit.
            "valueLen": str(visible_length(slide.raw("value", ""))),
            "label": rich_text(slide.raw("label", "")),
            "context": rich_text(slide.raw("context", "")),
            "title": rich_text(slide.raw("title", "")),
            "body": rich_text(slide.raw("body", "")),
            "myth": rich_text(slide.raw("myth", "")),
            "fact": rich_text(slide.raw("fact", "")),
            "line": rich_text(slide.raw("line", "")),
            "button": escape(slide.raw("button") or identity["defaultButton"]),
        }
