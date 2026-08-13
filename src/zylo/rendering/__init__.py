"""Deck to HTML.

Pure: every class here turns data into a string. Taking the screenshot is a
port, which means the exact HTML a slide produces can be asserted in a test
without launching a browser.
"""
from .assets import AssetEncoder, FontResolver
from .contact_sheet import ContactSheetHtmlBuilder, ContactSheetLayout
from .markup import escape, rich_text
from .slides import SlideHtmlBuilder
from .templates import TemplateRepository
from .theme import CssVariableBuilder, Theme

__all__ = [
    "AssetEncoder",
    "ContactSheetHtmlBuilder",
    "ContactSheetLayout",
    "CssVariableBuilder",
    "FontResolver",
    "SlideHtmlBuilder",
    "TemplateRepository",
    "Theme",
    "escape",
    "rich_text",
]
