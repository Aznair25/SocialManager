#!/usr/bin/env python3
"""Dump the observable behaviour of the pure functions in src/ to JSON.

Run against the pre-refactor tree to capture a baseline, then against the
refactored tree; the two files must be byte-identical. This is what proves the
restructure did not quietly change a validator message, an error ordering, a
slug or a title cleanup.

    python tools/capture_baseline.py before.json
    # ...refactor...
    python tools/capture_baseline.py after.json
    diff before.json after.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def _load():
    """Import whichever layout is present: flat modules or the zylo package."""
    try:
        from zylo.domain.deck import Deck
        from zylo.domain.validation import DeckValidator
        from zylo.services.generation import length_targets, verbatim_hits
        from zylo.services.naming import slugify
        from zylo.adapters.extraction import clean_body, clean_title

        from zylo.domain.errors import MalformedDeckError

        validator = DeckValidator.with_default_rules()

        def validate(d):
            try:
                report = validator.validate(Deck.from_dict(d))
            except MalformedDeckError as exc:
                return [str(exc)], []
            return list(report.errors), list(report.warnings)

        def lengths(d):
            return length_targets(Deck.from_dict(d))

        def verbatim(d, src):
            return verbatim_hits(Deck.from_dict(d), src)

        return validate, lengths, verbatim, slugify, clean_title, clean_body
    except ImportError:
        from validate import validate_deck
        from generate import length_targets, slugify, verbatim_hits
        from extract import _clean, _clean_title

        return validate_deck, length_targets, verbatim_hits, slugify, _clean_title, _clean


validate_deck, length_targets, verbatim_hits, slugify, clean_title, clean_body = _load()


def base(**kw):
    deck = {
        "id": "2026-08-07_a-deck",
        "archetype": "insight",
        "palette": "dark",
        "topic": "T",
        "pillar": "",
        "cta_target": "wearezylo.com",
        "slides": [
            {"role": "cover", "hook": "Your pilot is not a strategy"},
            {"role": "content", "title": "Governance arrives late", "body": "It lands after the build."},
            {"role": "content", "title": "Capability stays outside", "body": "The vendor keeps the knowledge."},
            {"role": "content", "title": "Adoption is the gap", "body": "Licences are not usage."},
            {"role": "cta", "line": "Where is your bottleneck?"},
        ],
        "caption": "Hook line\n\nBody line\n\nMore at wearezylo.com",
        "hashtags": ["AIConsulting", "EnterpriseAI", "AIGovernance", "AIAdoption", "AIStrategy"],
    }
    deck.update(kw)
    return deck


def slides(*roles_fields):
    return [dict(role=r, **f) for r, f in roles_fields]


CASES = {
    "valid_insight": base(),
    "not_a_dict": ["nope"],
    "bad_id": base(id="nope"),
    "bad_archetype": base(archetype="wat"),
    "bad_palette": base(palette="beige"),
    "too_few_slides": base(slides=base()["slides"][:3]),
    "too_many_slides": base(
        slides=slides(("cover", {"hook": "H"}), *[("content", {"title": "T", "body": "B"})] * 20, ("cta", {"line": "L"}))
    ),
    "warn_slide_count": base(
        slides=slides(("cover", {"hook": "H"}), *[("content", {"title": "T", "body": "B"})] * 10, ("cta", {"line": "L"}))
    ),
    "first_not_cover": base(
        slides=slides(("content", {"title": "T", "body": "B"}), *[("content", {"title": "T", "body": "B"})] * 3, ("cta", {"line": "L"}))
    ),
    "last_not_cta": base(
        slides=slides(("cover", {"hook": "H"}), *[("content", {"title": "T", "body": "B"})] * 4)
    ),
    "unknown_role": base(
        slides=slides(("cover", {"hook": "H"}), ("bogus", {"x": 1}), ("content", {"title": "T", "body": "B"}),
                      ("content", {"title": "T", "body": "B"}), ("cta", {"line": "L"}))
    ),
    "role_not_allowed": base(
        archetype="insight",
        slides=slides(("cover", {"hook": "H"}), ("stat", {"value": "3x", "label": "faster"}),
                      ("content", {"title": "T", "body": "B"}), ("content", {"title": "T", "body": "B"}),
                      ("cta", {"line": "L"})),
    ),
    "missing_required": base(
        slides=slides(("cover", {"hook": ""}), ("content", {"title": "T", "body": "B"}),
                      ("content", {"title": "T", "body": "B"}), ("content", {"title": "T", "body": "B"}),
                      ("cta", {"line": "L"}))
    ),
    "over_limit": base(
        slides=slides(("cover", {"hook": "x" * 80}), ("content", {"title": "y" * 60, "body": "z" * 260}),
                      ("content", {"title": "T", "body": "B"}), ("content", {"title": "T", "body": "B"}),
                      ("cta", {"line": "L"}))
    ),
    "unbalanced_markers": base(
        slides=slides(("cover", {"hook": "**broken hook"}), ("content", {"title": "T", "body": "B"}),
                      ("content", {"title": "T", "body": "B"}), ("content", {"title": "T", "body": "B"}),
                      ("cta", {"line": "L"}))
    ),
    "emoji_and_bang": base(
        slides=slides(("cover", {"hook": "Great 🚀"}), ("content", {"title": "Wow!", "body": "B"}),
                      ("content", {"title": "T", "body": "B"}), ("content", {"title": "T", "body": "B"}),
                      ("cta", {"line": "L"}))
    ),
    "stat_value_warn": base(
        archetype="stat",
        slides=slides(("cover", {"hook": "H"}), ("stat", {"value": "1234567", "label": "long"}),
                      ("stat", {"value": "3x", "label": "faster"}), ("stat", {"value": "50+", "label": "companies"}),
                      ("cta", {"line": "L"})),
    ),
    "duplicate_figure": base(
        archetype="stat",
        slides=slides(("cover", {"hook": "H"}), ("stat", {"value": "+85%", "label": "efficiency"}),
                      ("stat", {"value": "85%", "label": "pilots stall"}), ("stat", {"value": "3x", "label": "faster"}),
                      ("cta", {"line": "L"})),
    ),
    "count_promise_mismatch": base(
        slides=slides(("cover", {"hook": "5 signs you are stuck"}), ("content", {"title": "T", "body": "B"}),
                      ("content", {"title": "T", "body": "B"}), ("content", {"title": "T", "body": "B"}),
                      ("cta", {"line": "L"}))
    ),
    "count_promise_ok": base(
        slides=slides(("cover", {"hook": "3 signs you are stuck"}), ("content", {"title": "T", "body": "B"}),
                      ("content", {"title": "T", "body": "B"}), ("content", {"title": "T", "body": "B"}),
                      ("cta", {"line": "L"}))
    ),
    "count_promise_not_a_count": base(
        slides=slides(("cover", {"hook": "3x faster than before"}), ("content", {"title": "T", "body": "B"}),
                      ("content", {"title": "T", "body": "B"}), ("content", {"title": "T", "body": "B"}),
                      ("cta", {"line": "L"}))
    ),
    "stacked_cta": base(
        slides=base()["slides"][:4] + [{"role": "cta", "line": "One. Two. Three."}]
    ),
    "cta_setup_ok": base(
        slides=base()["slides"][:4] + [{"role": "cta", "line": "Two true? Let us talk."}]
    ),
    "no_caption": base(caption="   "),
    "caption_too_long": base(caption="x" * 2400),
    "hashtag_warn": base(hashtags=["OnlyOne"]),
    "hashtag_over_limit": base(hashtags=[f"tag{i}" for i in range(31)]),
    "mythfact_valid": base(
        archetype="mythfact",
        slides=slides(("cover", {"hook": "H"}), ("mythfact", {"myth": "M", "fact": "F"}),
                      ("mythfact", {"myth": "M2", "fact": "F2"}), ("mythfact", {"myth": "M3", "fact": "F3"}),
                      ("cta", {"line": "L"})),
    ),
}

SOURCE = (
    "Enterprises keep buying artificial intelligence licences without any plan for adoption at all. "
    "The governance framework usually arrives long after the first system is already in production."
)

VERBATIM_CASES = {
    "copied_run": base(
        slides=base()["slides"][:1]
        + [{"role": "content", "title": "T",
            "body": "The governance framework usually arrives long after the first system shipped."}]
        + base()["slides"][2:]
    ),
    "original": base(),
    "copied_caption": base(caption="Enterprises keep buying artificial intelligence licences without any plan"),
}

SLUGS = [
    ("How AI agents cut support costs", None),
    ("Agentic AI: Orchestrating Enterprise Operations", None),
    ("   ", None),
    ("Something", "manual-override"),
    ("A" * 120, None),
    ("...!!!...", None),
]

TITLES = [
    ("Foo - Wikipedia", "en.wikipedia.org"),
    ("Real Title - A Genuine Subtitle", "example.com"),
    ("Post | LinkedIn", "www.linkedin.com"),
    ("A" * 140, "example.com"),
    ("Short. Then more text that goes on well past the hundred character mark to force the sentence split path here.", "example.com"),
    ("", "example.com"),
]

BODIES = [
    "Sign in\nHome\nAbout\n\nA real paragraph of prose that should survive the cleaning pass intact.\nSign in\n",
    "  spaced   out   line  \n\n\nx\nyy\n5 min read\nAnother genuine sentence with enough words to be kept.",
]


def main(out):
    result = {
        "validate": {k: dict(zip(("errors", "warnings"), validate_deck(v))) for k, v in CASES.items()},
        "length_targets": {k: length_targets(v) for k, v in CASES.items() if isinstance(v, dict)},
        "verbatim": {k: verbatim_hits(v, SOURCE) for k, v in VERBATIM_CASES.items()},
        "slugify": {f"{t!r}|{o!r}": slugify(t, o) for t, o in SLUGS},
        "clean_title": {f"{t!r}|{n}": clean_title(t, n) for t, n in TITLES},
        "clean_body": {str(i): clean_body(b) for i, b in enumerate(BODIES)},
        "real_decks": {},
    }
    for f in sorted((ROOT / "decks").glob("*/deck.json")):
        deck = json.loads(f.read_text(encoding="utf-8"))
        e, w = validate_deck(deck)
        result["real_decks"][f.parent.name] = {"errors": e, "warnings": w}

    Path(out).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    n = sum(len(v["errors"]) for v in result["validate"].values())
    print(f"wrote {out}: {len(CASES)} validation cases, {n} errors captured")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "baseline.json")
