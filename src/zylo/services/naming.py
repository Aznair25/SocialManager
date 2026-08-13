"""Deck ids and topics.

The id is a filesystem path, a URL segment and a sort key at once, which is why
it is `YYYY-MM-DD_slug` and why the slug is aggressively narrowed to lowercase
ASCII.
"""
import datetime
import re
from typing import Callable

from ..domain.errors import GenerationError
from ..domain.source import SourceMaterial

SLUG_MAX_CHARS = 40
FALLBACK_SLUG = "deck"
FALLBACK_TOPIC = "source material"


def slugify(topic: str, override: str | None = None) -> str:
    if override:
        return override
    slug = re.sub(r"[^a-z0-9]+", "-", (topic or "").lower()).strip("-")
    return slug[:SLUG_MAX_CHARS].rstrip("-") or FALLBACK_SLUG


class DeckIdFactory:
    """Builds `YYYY-MM-DD_slug`. The clock is injected so tests are not date-dependent."""

    def __init__(self, today: Callable[[], datetime.date] = datetime.date.today):
        self._today = today

    def create(self, topic: str, slug: str | None = None) -> str:
        return f"{self._today().isoformat()}_{slugify(topic, slug)}"


class TopicResolver:
    """Works out what the deck is about.

    With source material the topic is optional: fall back to the page title, then
    to the opening line of the text — pasted posts often have no title at all.
    """

    def resolve(self, topic: str | None, source: SourceMaterial | None = None) -> str:
        resolved = (topic or "").strip()
        if not resolved and source:
            resolved = (source.title or "").strip()
        if not resolved and source and source.text:
            resolved = source.opening_sentence or FALLBACK_TOPIC
        if not resolved:
            raise GenerationError("Give a topic, or a source URL/text to draw one from")
        return resolved
