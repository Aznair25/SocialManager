"""The deck model must round-trip decks/ on disk without losing anything."""
import json
from pathlib import Path

import pytest

from zylo.config import Paths
from zylo.domain.deck import Archetype, Deck, Palette, Slide
from zylo.domain.errors import MalformedDeckError

from .conftest import deck_payload


def test_round_trips_a_payload_exactly():
    payload = deck_payload()
    assert Deck.from_dict(payload).to_dict() == payload


def test_round_trips_every_real_deck_on_disk():
    """The strongest guarantee available: nothing already shipped changes shape."""
    decks = sorted(Paths.discover().decks.glob("*/deck.json"))
    assert decks, "expected decks/ to contain at least one deck.json"
    for path in decks:
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert Deck.from_dict(raw).to_dict() == raw, path.parent.name


def test_preserves_unknown_top_level_keys():
    deck = Deck.from_dict(deck_payload(experiment="v2", another={"a": 1}))
    assert deck.extras == {"experiment": "v2", "another": {"a": 1}}
    assert deck.to_dict()["experiment"] == "v2"


def test_optional_keys_are_omitted_when_unset():
    out = Deck.from_dict(deck_payload()).to_dict()
    assert "framework" not in out
    assert "source_url" not in out


def test_optional_keys_survive_when_set():
    payload = deck_payload(framework="callout", source_url="https://example.com/post")
    assert Deck.from_dict(payload).to_dict() == payload


def test_rejects_something_that_is_not_an_object():
    with pytest.raises(MalformedDeckError, match="not an object"):
        Deck.from_dict(["not", "a", "deck"])


def test_missing_keys_fall_back_rather_than_raising():
    deck = Deck.from_dict({"id": "x"})
    assert deck.slides == [] and deck.hashtags == [] and deck.cta_target == "wearezylo.com"


class TestSlide:
    def test_strips_highlight_markers_from_text(self):
        s = Slide.from_dict({"role": "cover", "hook": "Your **pilot** is not a strategy"})
        assert s.raw("hook") == "Your **pilot** is not a strategy"
        assert s.text("hook") == "Your pilot is not a strategy"

    def test_distinguishes_absent_from_blank(self):
        s = Slide.from_dict({"role": "cta", "line": "   "})
        assert s.has("line") and s.is_blank("line")
        assert not s.has("button")

    def test_role_key_is_not_duplicated_into_fields(self):
        s = Slide.from_dict({"role": "cover", "hook": "H"})
        assert s.fields == {"hook": "H"}
        assert s.to_dict() == {"role": "cover", "hook": "H"}


class TestShapeHelpers:
    def test_middle_excludes_cover_and_cta(self, valid_deck):
        assert [s.role for s in valid_deck.middle] == ["content"] * 3

    def test_numbered_is_one_based(self, valid_deck):
        assert [i for i, _ in valid_deck.numbered()] == [1, 2, 3, 4, 5]

    def test_slides_with_role_reports_original_positions(self):
        deck = Deck.from_dict(deck_payload(archetype="stat", slides=[
            {"role": "cover", "hook": "H"},
            {"role": "stat", "value": "3x", "label": "faster"},
            {"role": "content", "title": "T", "body": "B"},
            {"role": "stat", "value": "50+", "label": "companies"},
            {"role": "cta", "line": "L"},
        ]))
        assert [i for i, _ in deck.slides_with_role("stat")] == [2, 4]


def test_enums_expose_the_choices_the_api_offers():
    assert Archetype.values() == ["insight", "mythfact", "stat"]
    assert Palette.values() == ["dark", "light"]


def test_paths_relative_falls_back_to_absolute_for_outside_paths():
    paths = Paths(Path("/tmp/project"))
    assert paths.relative(Path("/tmp/project/decks/x")) == "decks/x"
    assert paths.relative(Path("/etc/hosts")) == "/etc/hosts"
