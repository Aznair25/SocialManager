"""Per-field constraints.

Split out from the slide rule so a new content restriction is a new class in the
`DEFAULT_FIELD_CONSTRAINTS` list rather than another branch inside a loop. The
list order is the order the messages come out in.
"""
import re
from dataclasses import dataclass
from typing import Any, Iterable, Protocol, runtime_checkable

from ..text import markers_balanced, strip_markers, visible_length
from .report import Issue, error

EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


@dataclass(frozen=True)
class FieldContext:
    """One field of one slide, with everything a constraint needs to judge it."""

    index: int          # 1-based slide number, as it appears in messages
    role: str
    name: str
    raw: Any            # the stored value, highlight markers intact
    limit: int          # max visible characters for this field

    @property
    def text(self) -> str:
        """What the reader sees — markers stripped."""
        return strip_markers(self.raw)

    @property
    def where(self) -> str:
        return f"slide {self.index} ({self.role}).{self.name}"


@runtime_checkable
class FieldConstraint(Protocol):
    def check(self, ctx: FieldContext) -> Iterable[Issue]:
        ...


class MaxLength:
    """The template's type size is fixed; overflowing copy gets rewritten, not shrunk."""

    def check(self, ctx: FieldContext) -> Iterable[Issue]:
        length = visible_length(ctx.raw)
        if length > ctx.limit:
            yield error(f"{ctx.where}: {length} chars > {ctx.limit} — "
                        f"rewrite the copy, never shrink the type")


class BalancedHighlights:
    """An odd number of ** markers renders a literal asterisk on the slide."""

    def check(self, ctx: FieldContext) -> Iterable[Issue]:
        if not markers_balanced(ctx.raw):
            yield error(f"{ctx.where}: unbalanced ** highlight markers")


class NoEmoji:
    def check(self, ctx: FieldContext) -> Iterable[Issue]:
        if EMOJI_RE.search(ctx.text):
            yield error(f"{ctx.where}: emojis are forbidden on slides")


class NoExclamation:
    """Enterprise-calm voice: the deck states things, it does not shout them."""

    def check(self, ctx: FieldContext) -> Iterable[Issue]:
        if "!" in ctx.text:
            yield error(f"{ctx.where}: exclamation marks are forbidden on slides")


def default_field_constraints() -> list[FieldConstraint]:
    return [MaxLength(), BalancedHighlights(), NoEmoji(), NoExclamation()]
