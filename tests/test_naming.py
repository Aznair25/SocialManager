"""Deck ids, slugs and topic resolution."""
import datetime

import pytest

from zylo.domain.errors import GenerationError
from zylo.domain.source import SourceMaterial
from zylo.services.naming import DeckIdFactory, TopicResolver, slugify

from .conftest import FIXED_DATE


class TestSlugify:
    @pytest.mark.parametrize("topic,expected", [
        ("How AI agents cut support costs", "how-ai-agents-cut-support-costs"),
        ("Agentic AI: Orchestrating Enterprise Operations",
         "agentic-ai-orchestrating-enterprise-oper"),
        ("Trailing punctuation!!!", "trailing-punctuation"),
    ])
    def test_narrows_to_lowercase_ascii(self, topic, expected):
        assert slugify(topic) == expected

    def test_caps_at_forty_characters_without_a_trailing_dash(self):
        slug = slugify("A" * 120)
        assert len(slug) == 40 and not slug.endswith("-")

    @pytest.mark.parametrize("topic", ["", "   ", "...!!!..."])
    def test_falls_back_when_nothing_survives(self, topic):
        assert slugify(topic) == "deck"

    def test_an_override_wins_outright(self):
        assert slugify("Something else entirely", "manual-override") == "manual-override"


class TestDeckIdFactory:
    def test_combines_the_date_and_the_slug(self):
        factory = DeckIdFactory(lambda: FIXED_DATE)
        assert factory.create("Adoption is the gap") == "2026-08-12_adoption-is-the-gap"

    def test_uses_the_real_clock_by_default(self):
        assert DeckIdFactory().create("x").startswith(datetime.date.today().isoformat())


class TestTopicResolver:
    def test_an_explicit_topic_wins(self):
        source = SourceMaterial(text="body", title="Source title")
        assert TopicResolver().resolve("  My topic  ", source) == "My topic"

    def test_falls_back_to_the_source_title(self):
        source = SourceMaterial(text="body", title="Source title")
        assert TopicResolver().resolve(None, source) == "Source title"

    def test_falls_back_to_the_opening_sentence_when_there_is_no_title(self):
        """Pasted posts often have no title at all."""
        source = SourceMaterial(
            text="short\nEnterprises keep buying licences with no plan. And then more text.")
        assert TopicResolver().resolve("", source) == "Enterprises keep buying licences with no plan."

    def test_falls_back_to_a_placeholder_when_the_text_has_no_long_line(self):
        assert TopicResolver().resolve("", SourceMaterial(text="tiny")) == "source material"

    def test_raises_when_there_is_nothing_to_go_on(self):
        with pytest.raises(GenerationError, match="Give a topic"):
            TopicResolver().resolve(None, None)


class TestSourceMaterial:
    def test_from_text_strips_and_is_falsey_when_empty(self):
        assert not SourceMaterial.from_text("   ")
        assert SourceMaterial.from_text("  body  ").text == "body"

    def test_from_dict_tolerates_none_and_passthrough(self):
        assert SourceMaterial.from_dict(None) is None
        existing = SourceMaterial(text="t")
        assert SourceMaterial.from_dict(existing) is existing
        assert SourceMaterial.from_dict({"text": " t "}).text == "t"
