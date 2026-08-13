"""The contact sheet — every slide as a thumbnail on one reviewable image.

This is the artefact a human actually looks at before uploading, so it carries
the deck id, archetype and palette in a header bar.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ..domain.deck import Deck
from .assets import AssetEncoder, FontResolver
from .markup import document, escape
from .theme import Theme


@dataclass(frozen=True)
class ContactSheetLayout:
    """Grid geometry. Every dimension the sheet needs is derived from these."""

    columns: int = 4
    thumb_width: int = 250
    gap: int = 20
    padding: int = 32
    header: int = 88
    slide_width: int = 1080
    slide_height: int = 1350

    @classmethod
    def for_theme(cls, theme: Theme, **overrides) -> "ContactSheetLayout":
        return cls(slide_width=theme.width, slide_height=theme.height, **overrides)

    @property
    def thumb_height(self) -> int:
        return round(self.thumb_width * self.slide_height / self.slide_width)

    def rows(self, count: int) -> int:
        return -(-count // self.columns)   # ceiling division

    def width(self) -> int:
        return self.padding * 2 + self.columns * self.thumb_width + (self.columns - 1) * self.gap

    def height(self, count: int) -> int:
        rows = self.rows(count)
        return (self.header + self.padding + rows * self.thumb_height
                + (rows - 1) * self.gap + self.padding + self.padding // 2)


class ContactSheetHtmlBuilder:
    def __init__(self, theme: Theme, fonts: FontResolver, layout: ContactSheetLayout | None = None):
        self._theme = theme
        self._fonts = fonts
        self._layout = layout or ContactSheetLayout.for_theme(theme)

    def build(self, deck: Deck, slide_pngs: Sequence[Path]) -> tuple[str, int, int]:
        """Returns (html, viewport width, viewport height)."""
        width = self._layout.width()
        height = self._layout.height(len(slide_pngs))
        html = document(head=self._fonts.head_html(),
                        css=self._css(width),
                        body=self._body(deck, slide_pngs))
        return html, width, height

    def _figures(self, slide_pngs: Sequence[Path]) -> str:
        # Inlined as data URIs: set_content() pages have an about:blank origin, from
        # which Chromium refuses to load file:// subresources.
        layout = self._layout
        return "".join(
            '<figure><img src="%s" width="%d" height="%d"><figcaption>%02d</figcaption></figure>'
            % (AssetEncoder.data_uri(path), layout.thumb_width, layout.thumb_height, i + 1)
            for i, path in enumerate(slide_pngs)
        )

    def _css(self, width: int) -> str:
        layout, color = self._layout, self._theme.color
        return (
            "*{margin:0;box-sizing:border-box}body{width:%dpx;background:%s;font-family:'Poppins',sans-serif;padding:%dpx}"
            ".bar{height:%dpx;display:flex;align-items:center;justify-content:space-between;color:#fff}"
            ".bar .t{font-size:26px;font-weight:600}.bar .m{font-size:20px;color:%s}"
            ".grid{display:grid;grid-template-columns:repeat(%d,%dpx);gap:%dpx;margin-top:%dpx}"
            "figure{position:relative}img{display:block;border-radius:8px}"
            "figcaption{position:absolute;top:8px;left:8px;background:rgba(0,0,0,.55);color:#fff;font-size:16px;padding:2px 10px;border-radius:999px}"
            % (width, color["bgDarkSection"], layout.padding, layout.header - layout.padding,
               color["fgMutedOnDark"], layout.columns, layout.thumb_width, layout.gap,
               layout.padding // 2)
        )

    def _body(self, deck: Deck, slide_pngs: Sequence[Path]) -> str:
        return (
            '<div class="bar"><span class="t">%s</span>'
            '<span class="m">%s · %s · %d slides · review before upload</span></div>'
            '<div class="grid">%s</div>'
            % (escape(deck.id), deck.archetype, deck.palette, len(slide_pngs),
               self._figures(slide_pngs))
        )
