"""Checks that produce instructions for the model rather than verdicts on a deck."""
import pytest

from zylo.domain.deck import Deck
from zylo.services.critique import JsonExtractor, LengthTargetAdvisor, VerbatimOverlapDetector

from .conftest import deck_payload, slide

SOURCE = (
    "Enterprises keep buying artificial intelligence licences without any plan for adoption. "
    "The governance framework usually arrives long after the first system is in production."
)


def build(**overrides):
    return Deck.from_dict(deck_payload(**overrides))


class TestVerbatimOverlap:
    def test_flags_a_copied_run_of_seven_words(self):
        deck = build(slides=[
            slide("cover", hook="H"),
            slide("content", title="T",
                  body="The governance framework usually arrives long after the build."),
            slide("content", title="T2", body="B2"),
            slide("content", title="T3", body="B3"),
            slide("cta", line="L"),
        ])
        hits = VerbatimOverlapDetector().hits(deck, SOURCE)
        assert len(hits) == 1
        assert hits[0].startswith("slide 2 (content).body: copied wording from the source")
        assert "Rewrite this in your own words" in hits[0]

    def test_original_wording_passes(self, valid_deck):
        assert VerbatimOverlapDetector().hits(valid_deck, SOURCE) == []

    def test_checks_the_caption_too(self):
        deck = build(caption="Enterprises keep buying artificial intelligence licences without any plan")
        hits = VerbatimOverlapDetector().hits(deck, SOURCE)
        assert len(hits) == 1 and hits[0].startswith("caption:")

    def test_reports_each_field_once_not_once_per_overlap(self):
        deck = build(slides=[
            slide("cover", hook="H"),
            slide("content", title="T", body=SOURCE[:190]),
            slide("content", title="T2", body="B2"),
            slide("content", title="T3", body="B3"),
            slide("cta", line="L"),
        ])
        assert len(VerbatimOverlapDetector().hits(deck, SOURCE)) == 1

    def test_short_sources_cannot_produce_a_match(self, valid_deck):
        assert VerbatimOverlapDetector().hits(valid_deck, "three short words") == []

    def test_ngram_length_is_configurable(self):
        deck = build(slides=[
            slide("cover", hook="H"),
            slide("content", title="T", body="without any plan"),
            slide("content", title="T2", body="B2"),
            slide("content", title="T3", body="B3"),
            slide("cta", line="L"),
        ])
        assert VerbatimOverlapDetector(ngram=7).hits(deck, SOURCE) == []
        assert VerbatimOverlapDetector(ngram=3).hits(deck, SOURCE) != []


class TestLengthTargets:
    def test_names_a_target_well_under_the_limit(self):
        """Told only the limit, the model shaves three characters and lands over again."""
        deck = build(slides=[slide("cover", hook="x" * 80),
                             slide("content", title="T", body="B"),
                             slide("content", title="T2", body="B2"),
                             slide("content", title="T3", body="B3"),
                             slide("cta", line="L")])
        targets = LengthTargetAdvisor().targets(deck)
        assert targets == ["slide 1 (cover).hook is 80 characters. Rewrite it to at most "
                           "30 characters — cut a clause, keep the point."]

    def test_says_nothing_about_fields_that_fit(self, valid_deck):
        assert LengthTargetAdvisor().targets(valid_deck) == []

    def test_target_never_drops_below_the_floor(self):
        deck = build(slides=[slide("cover", hook="H"), slide("content", title="T", body="B"),
                             slide("content", title="T2", body="B2"),
                             slide("content", title="T3", body="B3"),
                             slide("cta", line="L", button="x" * 40)])
        assert "at most 20 characters" in LengthTargetAdvisor(margin=100).targets(deck)[0]


class TestJsonExtractor:
    @pytest.mark.parametrize("raw", [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        '```\n{"a": 1}\n```',
        'Here you go:\n{"a": 1}\nHope that helps.',
    ])
    def test_finds_the_object_through_fences_and_chatter(self, raw):
        assert JsonExtractor().extract(raw) == {"a": 1}

    @pytest.mark.parametrize("raw", ["", "no object here", "}{"])
    def test_raises_when_there_is_no_object(self, raw):
        with pytest.raises(ValueError, match="no JSON object"):
            JsonExtractor().extract(raw)

    def test_propagates_malformed_json(self):
        import json

        with pytest.raises(json.JSONDecodeError):
            JsonExtractor().extract('{"a": }')
