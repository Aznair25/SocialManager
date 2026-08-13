"""Request and response shapes for the HTTP API.

Field limits here are a first line of defence only — the real rules live in the
domain validator, which the CLI goes through too.
"""
from pydantic import BaseModel, Field

from ..domain.deck import Deck
from ..prompts.frameworks import AUTO
from ..services.pipeline import DeckBrief


class DeckRequest(BaseModel):
    """A deck to build. Either a topic, or reference material to draw one from."""

    topic: str | None = Field(default=None, max_length=300)
    archetype: str = "insight"
    palette: str = "dark"
    notes: str | None = Field(default=None, max_length=1000)
    slug: str | None = None
    pillar: str | None = None
    framework: str = AUTO
    # Optional reference material: a URL to read, or text pasted in when a site blocks the fetch.
    source_url: str | None = Field(default=None, max_length=2000)
    source_text: str | None = Field(default=None, max_length=40000)

    @property
    def has_source(self) -> bool:
        return bool((self.source_url or "").strip() or (self.source_text or "").strip())

    def to_brief(self) -> DeckBrief:
        return DeckBrief(
            topic=self.topic, archetype=self.archetype, palette=self.palette,
            notes=self.notes, slug=self.slug, pillar=self.pillar,
            framework=self.framework, source_url=self.source_url,
            source_text=self.source_text,
        )


def deck_summary(deck_id: str, deck: Deck, rendered: bool) -> dict:
    """The compact shape the deck list renders from."""
    return {
        "id": deck.id or deck_id,
        "topic": deck.topic,
        "archetype": deck.archetype,
        "palette": deck.palette,
        "slides": deck.slide_count,
        "rendered": rendered,
    }
