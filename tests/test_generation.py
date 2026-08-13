"""The generation loop, driven by a fake model.

The correction loop is the part most worth pinning down: a rejected deck has to
come back with the errors attached, and identity fields have to stay code-owned
no matter what the model returns.
"""
import json

import pytest

from zylo.domain.errors import GenerationError
from zylo.domain.source import SourceMaterial
from zylo.domain.validation import DeckValidator
from zylo.services.generation import DeckGenerationService, GenerationRequest
from zylo.services.naming import DeckIdFactory

from .conftest import FIXED_DATE, deck_payload, slide
from .fakes import FakeChatClient, RecordingReporter


def reply(**overrides) -> str:
    payload = deck_payload(**overrides)
    return json.dumps({"slides": payload["slides"], "caption": payload["caption"],
                       "hashtags": payload["hashtags"]})


def bad_reply() -> str:
    return reply(slides=[slide("cover", hook="x" * 90),
                         slide("content", title="T", body="B"),
                         slide("content", title="T2", body="B2"),
                         slide("content", title="T3", body="B3"),
                         slide("cta", line="L")])


def service(replies, **kwargs) -> tuple[DeckGenerationService, FakeChatClient]:
    chat = FakeChatClient(replies)
    return DeckGenerationService(chat=chat, validator=DeckValidator.with_default_rules(),
                                 ids=DeckIdFactory(lambda: FIXED_DATE), **kwargs), chat


class TestHappyPath:
    def test_returns_a_validated_deck_on_the_first_attempt(self):
        gen, chat = service([reply()])
        deck = gen.generate(GenerationRequest(topic="Adoption is the gap"))
        assert deck.id == "2026-08-12_adoption-is-the-gap"
        assert chat.call_count == 1

    def test_sends_a_system_prompt_and_a_brief(self):
        gen, chat = service([reply()])
        gen.generate(GenerationRequest(topic="Adoption", palette="light", notes="be blunt"))
        system, user = chat.calls[0]
        assert system.role == "system" and "Zylo" in system.content
        assert user.role == "user"
        assert "Topic: Adoption" in user.content
        assert "Palette: light" in user.content
        assert "Direction notes: be blunt" in user.content

    def test_reports_success(self):
        gen, _ = service([reply()])
        reporter = RecordingReporter()
        gen.generate(GenerationRequest(topic="Adoption"), reporter)
        assert "  ✓ valid on attempt 1" in reporter.messages


class TestIdentityIsCodeOwned:
    """The model writes copy. It never gets to set who the deck is."""

    def test_model_supplied_identity_fields_are_ignored(self):
        rogue = json.dumps({
            "id": "hacked", "archetype": "stat", "palette": "light",
            "cta_target": "evil.com", "topic": "not this",
            **json.loads(reply()),
        })
        gen, _ = service([rogue])
        deck = gen.generate(GenerationRequest(topic="Adoption", archetype="insight",
                                              palette="dark"))
        assert deck.id == "2026-08-12_adoption"
        assert (deck.archetype, deck.palette, deck.topic) == ("insight", "dark", "Adoption")
        assert deck.cta_target == "wearezylo.com"

    def test_an_explicit_slug_overrides_the_derived_one(self):
        gen, _ = service([reply()])
        deck = gen.generate(GenerationRequest(topic="Adoption", slug="custom-slug"))
        assert deck.id == "2026-08-12_custom-slug"

    def test_framework_is_recorded_only_when_it_was_chosen(self):
        gen, _ = service([reply(), reply()])
        assert gen.generate(GenerationRequest(topic="T")).framework is None
        assert gen.generate(GenerationRequest(topic="T", framework="callout")).framework == "callout"

    def test_source_url_is_kept_as_provenance(self):
        gen, _ = service([reply()])
        source = SourceMaterial(text="a" * 400, url="https://example.com/post", title="T")
        deck = gen.generate(GenerationRequest(topic="Adoption", source=source))
        assert deck.source_url == "https://example.com/post"


class TestCorrectionLoop:
    def test_retries_with_the_errors_attached(self):
        gen, chat = service([bad_reply(), reply()])
        reporter = RecordingReporter()
        deck = gen.generate(GenerationRequest(topic="Adoption"), reporter)

        assert deck.slides[0].raw("hook") == "Your pilot is not a strategy"
        assert chat.call_count == 2
        correction = chat.last_user_message()
        assert "Rejected:" in correction
        assert "90 chars > 55" in correction
        assert "  attempt 1: 1 validation error(s)" in reporter.messages

    def test_attaches_a_concrete_length_target(self):
        """Told only the limit, the model lands one character over again."""
        gen, chat = service([bad_reply(), reply()])
        gen.generate(GenerationRequest(topic="Adoption"))
        assert "Rewrite it to at most 30 characters" in chat.last_user_message()

    def test_retries_unparseable_output(self):
        gen, chat = service(["I am afraid I cannot do that", reply()])
        reporter = RecordingReporter()
        gen.generate(GenerationRequest(topic="Adoption"), reporter)
        assert chat.call_count == 2
        assert "  attempt 1: unparseable output, retrying" in reporter.messages
        assert "was not parseable JSON" in chat.last_user_message()

    def test_gives_up_after_the_attempt_limit(self):
        gen, chat = service([bad_reply()] * 3)
        with pytest.raises(GenerationError, match="still invalid after 3 attempts"):
            gen.generate(GenerationRequest(topic="Adoption"))
        assert chat.call_count == 3

    def test_attempt_limit_is_configurable(self):
        gen, chat = service([bad_reply()] * 2, max_attempts=2)
        with pytest.raises(GenerationError, match="after 2 attempts"):
            gen.generate(GenerationRequest(topic="Adoption"))
        assert chat.call_count == 2

    def test_never_parsing_still_raises_a_clean_error(self):
        """Not a NameError — this path used to leave the error list unbound."""
        gen, _ = service(["nonsense"] * 3)
        with pytest.raises(GenerationError, match="still invalid after 3 attempts"):
            gen.generate(GenerationRequest(topic="Adoption"))

    def test_warnings_are_reported_but_do_not_trigger_a_retry(self):
        gen, chat = service([reply(hashtags=["OnlyOne"])])
        reporter = RecordingReporter()
        gen.generate(GenerationRequest(topic="Adoption"), reporter)
        assert chat.call_count == 1
        assert "  WARN  hashtags: 1 — aim for 5-10" in reporter.messages


class TestCopiedWording:
    SOURCE = ("Enterprises keep buying artificial intelligence licences without any plan. "
              "The governance framework usually arrives long after the first system ships. "
              "That is the pattern across almost every transformation programme we see.")

    def copied(self):
        return reply(slides=[
            slide("cover", hook="H"),
            slide("content", title="T",
                  body="The governance framework usually arrives long after the build."),
            slide("content", title="T2", body="B2"),
            slide("content", title="T3", body="B3"),
            slide("cta", line="L"),
        ])

    def test_copied_phrasing_is_rejected_like_a_limit_breach(self):
        gen, chat = service([self.copied(), reply()])
        reporter = RecordingReporter()
        source = SourceMaterial(text=self.SOURCE, url="https://example.com/post")
        gen.generate(GenerationRequest(topic="Adoption", source=source), reporter)

        assert chat.call_count == 2
        assert "  attempt 1: 1 passage(s) copied from the source" in reporter.messages

    def test_success_message_confirms_original_wording(self):
        gen, _ = service([reply()])
        reporter = RecordingReporter()
        source = SourceMaterial(text=self.SOURCE)
        gen.generate(GenerationRequest(topic="Adoption", source=source), reporter)
        assert "  ✓ valid on attempt 1 (original wording confirmed)" in reporter.messages

    def test_the_source_is_included_in_the_brief(self):
        gen, chat = service([reply()])
        source = SourceMaterial(text=self.SOURCE, title="Original headline")
        gen.generate(GenerationRequest(topic="Adoption", source=source))
        brief = chat.calls[0][-1].content
        assert "SOURCE MATERIAL" in brief and "<<<SOURCE" in brief
        assert "Title: Original headline" in brief
