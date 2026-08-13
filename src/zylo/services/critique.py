"""Checks that run alongside validation and feed the same correction loop.

Both of these produce *instructions to the model*, not verdicts about a deck,
which is why they live here rather than in the domain rules: a hand-written deck
is not wrong for lacking them.
"""
import re
from typing import Sequence

from ..domain.deck import Deck
from ..domain.text import visible_length, words
from ..domain.validation import spec_for

#: Consecutive words. Slide bodies cap at 200 chars (~30 words), so 7 is a real lift.
DEFAULT_NGRAM = 7

#: Fields that carry model-written copy.
COPY_FIELDS = ("hook", "kicker", "value", "label", "context", "title", "body",
               "myth", "fact", "line")


class VerbatimOverlapDetector:
    """Finds slide or caption text sharing an n-word run with the source.

    The prompt asks for original wording; this is what makes it stick. Hits are
    fed back into the same correction loop the validator uses, so copied phrasing
    is rejected exactly like a character-limit breach.
    """

    def __init__(self, ngram: int = DEFAULT_NGRAM):
        self._n = ngram

    def hits(self, deck: Deck, source_text: str) -> list[str]:
        source_words = words(source_text)
        if len(source_words) < self._n:
            return []
        grams = {tuple(source_words[i:i + self._n])
                 for i in range(len(source_words) - self._n + 1)}

        found = []
        for where, text in self._targets(deck):
            overlap = self._first_overlap(text, grams)
            if overlap:
                found.append(f'{where}: copied wording from the source — "{overlap}…". '
                             f"Rewrite this in your own words, keeping the point.")
        return found

    def _targets(self, deck: Deck):
        for i, slide in deck.numbered():
            for name in COPY_FIELDS:
                if slide.raw(name):
                    yield f"slide {i} ({slide.role}).{name}", slide.raw(name)
        yield "caption", deck.caption

    def _first_overlap(self, text, grams) -> str | None:
        w = words(text)
        for i in range(max(0, len(w) - self._n + 1)):
            gram = tuple(w[i:i + self._n])
            if gram in grams:
                return " ".join(gram)
        return None


class LengthTargetAdvisor:
    """Turns "203 chars > 200" into a target the model can actually hit.

    Told only the limit, the model tries to shave exactly three characters — which
    it cannot count reliably — and lands 1-3 over again. Naming a target well
    under the limit converges instead.
    """

    def __init__(self, margin: int = 25, floor: int = 20):
        self._margin = margin
        self._floor = floor

    def targets(self, deck: Deck) -> list[str]:
        out = []
        for i, slide in deck.numbered():
            spec = spec_for(slide.role)
            if not spec:
                continue
            for name, limit in spec.limits.items():
                if not slide.has(name):
                    continue
                length = visible_length(slide.raw(name))
                if length > limit:
                    target = max(self._floor, limit - self._margin)
                    out.append(f"slide {i} ({slide.role}).{name} is {length} characters. "
                               f"Rewrite it to at most {target} characters — "
                               f"cut a clause, keep the point.")
        return out


class JsonExtractor:
    """Pulls the JSON object out of a model reply that may be fenced or chatty."""

    FENCE_RE = re.compile(r"^```(?:json)?|```$", re.MULTILINE)

    def extract(self, text: str) -> dict:
        import json

        cleaned = self.FENCE_RE.sub("", (text or "").strip()).strip()
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object in model output")
        return json.loads(cleaned[start:end + 1])


def joined(*groups: Sequence[str]) -> list[str]:
    """Flatten correction lists, preserving order."""
    return [item for group in groups for item in group]
