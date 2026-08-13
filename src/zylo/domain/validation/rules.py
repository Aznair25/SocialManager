"""Deck validation rules.

Each rule is an object answering one question about a deck, so adding a rule
means adding a class and listing it — no edits to the validator. The order in
`default_rules()` is the order issues are reported in, and the generator feeds
that error list straight back to the model, so it is kept stable.
"""
import re
from typing import Iterable, Protocol, runtime_checkable

from ..deck import Archetype, Deck, Palette
from ..text import visible_length
from .constraints import FieldConstraint, FieldContext, default_field_constraints
from .report import Issue, error, warning
from .specs import (
    HASHTAG_HARD_CAP,
    MAX_CAPTION_CHARS,
    MAX_HASHTAGS,
    MAX_SLIDES,
    MIDDLE_ROLES,
    MIN_HASHTAGS,
    MIN_SLIDES,
    RECOMMENDED_MAX_SLIDES,
    STAT_VALUE_COMFORTABLE,
    spec_for,
)

ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-z0-9-]+$")
# A hook that OPENS with a small number is a counted promise ("5 signs ..."), and the
# deck must deliver exactly that many. Guard against 3x / 40% / 2026, which are figures,
# not counts.
COUNT_PROMISE_RE = re.compile(r"^\s*(\d{1,2})(?![%×xX\d])\s+\S")
SENTENCE_END_RE = re.compile(r"[.!?](?=\s|$)")


@runtime_checkable
class ValidationRule(Protocol):
    """One question asked of a whole deck."""

    def check(self, deck: Deck) -> Iterable[Issue]:
        ...


class DeckIdFormat:
    """A warning, not an error: a hand-written deck with an odd id still renders."""

    def check(self, deck: Deck) -> Iterable[Issue]:
        if not ID_RE.match(deck.id or ""):
            yield warning(f'id "{deck.id}" should match YYYY-MM-DD_slug')


class KnownArchetype:
    def check(self, deck: Deck) -> Iterable[Issue]:
        if deck.archetype not in Archetype.values():
            yield error(f'archetype "{deck.archetype}" invalid')


class KnownPalette:
    def check(self, deck: Deck) -> Iterable[Issue]:
        if deck.palette not in Palette.values():
            yield error(f'palette "{deck.palette}" invalid')


class SlideCount:
    def check(self, deck: Deck) -> Iterable[Issue]:
        n = deck.slide_count
        if n < MIN_SLIDES:
            yield error(f"needs >={MIN_SLIDES} slides (cover + content + cta), got {n}")
        if n > MAX_SLIDES:
            yield error(f"Instagram cap is {MAX_SLIDES} slides, got {n}")
        elif n > RECOMMENDED_MAX_SLIDES:
            yield warning(f"{n} slides — 6-{RECOMMENDED_MAX_SLIDES} recommended")


class SlideSequence:
    """Every deck opens on a cover and closes on a cta."""

    def check(self, deck: Deck) -> Iterable[Issue]:
        if not deck.slides:
            return
        if deck.slides[0].role != "cover":
            yield error('slides[0] must be role "cover"')
        if deck.slides[-1].role != "cta":
            yield error('last slide must be role "cta"')


class SlideContent:
    """Per-slide checks: role is known and allowed, required fields present, each
    field within its constraints.

    Kept as one rule that walks the slides once so messages come out grouped by
    slide — which is how the model reads them when correcting. The per-field
    checks are injected, so extending them does not mean editing this class.
    """

    def __init__(self, constraints: list[FieldConstraint] | None = None):
        self._constraints = constraints or default_field_constraints()

    def check(self, deck: Deck) -> Iterable[Issue]:
        total = deck.slide_count
        allowed = MIDDLE_ROLES.get(deck.archetype)

        for i, slide in deck.numbered():
            spec = spec_for(slide.role)
            if spec is None:
                yield error(f'slide {i}: unknown role "{slide.role}"')
                continue

            if 1 < i < total and allowed and slide.role not in allowed:
                yield error(f'slide {i}: role "{slide.role}" not allowed '
                            f'in archetype "{deck.archetype}"')

            for name in spec.required:
                if slide.is_blank(name):
                    yield error(f'slide {i} ({slide.role}): missing required field "{name}"')

            for name, limit in spec.limits.items():
                if not slide.has(name):
                    continue
                ctx = FieldContext(index=i, role=slide.role, name=name,
                                   raw=slide.raw(name), limit=limit)
                for constraint in self._constraints:
                    yield from constraint.check(ctx)

            if slide.role == "stat" and visible_length(slide.raw("value", "")) > STAT_VALUE_COMFORTABLE:
                yield warning(f'slide {i}: stat value "{slide.raw("value")}" '
                              f">{STAT_VALUE_COMFORTABLE} chars renders smaller")


class UniqueFigures:
    """One figure, one claim.

    Reusing a real Zylo number for a second, different claim is how invented
    statistics get in — "+85% operational efficiency" quietly becomes "85% of AI
    pilots stall".
    """

    def check(self, deck: Deck) -> Iterable[Issue]:
        seen: dict[str, tuple[int, str]] = {}
        for i, slide in deck.slides_with_role("stat"):
            if not slide.raw("value"):
                continue
            core = re.sub(r"[^0-9]", "", slide.text("value"))
            if not core:
                continue
            if core in seen:
                j, previous = seen[core]
                yield error(f'slides {j} and {i} both use the figure "{core}" for different claims '
                            f'("{previous}" vs "{slide.text("label", "")}") — a figure belongs to one claim. '
                            f"Drop the invented one; never reuse a real number for a second statistic")
            else:
                seen[core] = (i, slide.text("label", ""))


class CountPromise:
    """A count on the cover is a promise the reader can check — deliver it exactly."""

    def check(self, deck: Deck) -> Iterable[Issue]:
        cover = deck.cover
        if cover is None or cover.role != "cover":
            return
        match = COUNT_PROMISE_RE.match(cover.text("hook", ""))
        if not match:
            return
        promised, delivered = int(match.group(1)), max(0, deck.slide_count - 2)
        if 1 < promised <= MAX_SLIDES and promised != delivered:
            yield error(f"cover promises {promised} but the deck delivers {delivered} — "
                        f"make the counts match exactly (add or cut slides, or change the number)")


class SingleAsk:
    """One ask on the cta, not three.

    A setup plus an ask ("Two of these true? Let's talk.") is one ask and stays
    legal; three clauses is a stacked cta.
    """

    def check(self, deck: Deck) -> Iterable[Issue]:
        closing = deck.closing
        if closing is None or closing.role != "cta":
            return
        line = closing.text("line", "").strip()
        if len(SENTENCE_END_RE.findall(line)) > 2:
            yield error(f"slide {deck.slide_count} (cta).line stacks multiple asks — "
                        f"a cta makes ONE ask (a single setup clause before it is fine)")


class CaptionPresent:
    def check(self, deck: Deck) -> Iterable[Issue]:
        if not str(deck.caption or "").strip():
            yield error("caption is required")
        elif len(deck.caption) > MAX_CAPTION_CHARS:
            yield error(f"caption {len(deck.caption)} chars > {MAX_CAPTION_CHARS} (Instagram limit)")


class HashtagCount:
    def check(self, deck: Deck) -> Iterable[Issue]:
        n = len(deck.hashtags)
        if not (MIN_HASHTAGS <= n <= MAX_HASHTAGS):
            yield warning(f"hashtags: {n} — aim for {MIN_HASHTAGS}-{MAX_HASHTAGS}")
        if n > HASHTAG_HARD_CAP:
            yield error(f"hashtags exceed Instagram limit of {HASHTAG_HARD_CAP}")


def default_rules() -> list[ValidationRule]:
    """The full rule set, in reporting order."""
    return [
        DeckIdFormat(),
        KnownArchetype(),
        KnownPalette(),
        SlideCount(),
        SlideSequence(),
        SlideContent(),
        UniqueFigures(),
        CountPromise(),
        SingleAsk(),
        CaptionPresent(),
        HashtagCount(),
    ]
