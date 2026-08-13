"""Topic (or source material) -> a validated Deck.

The model is the content brain ONLY: it writes slides, caption and hashtags.
Identity fields — id, archetype, palette, pillar, cta_target — are set by code,
so a hallucinated id or a drifted palette is structurally impossible.

Output is validated, and every rejection (character limits, forbidden emoji,
copied wording) goes back to the model as a numbered correction list.
"""
import json
from dataclasses import dataclass, field
from typing import Sequence

from ..domain.deck import Deck
from ..domain.errors import GenerationError
from ..domain.source import SourceMaterial
from ..domain.validation import DeckValidator
from ..ports import ChatClient
from ..prompts.builder import Message, PromptBuilder
from ..prompts.frameworks import AUTO
from ..reporting import ProgressReporter, resolve
from .critique import JsonExtractor, LengthTargetAdvisor, VerbatimOverlapDetector
from .naming import DeckIdFactory, TopicResolver

DEFAULT_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class GenerationRequest:
    """Everything the generator needs. Validated at the delivery boundary."""

    topic: str = ""
    archetype: str = "insight"
    palette: str = "dark"
    slug: str | None = None
    pillar: str | None = None
    notes: str | None = None
    framework: str = AUTO
    source: SourceMaterial | None = None

    @property
    def source_text(self) -> str:
        return self.source.text if self.source else ""


@dataclass
class _Attempt:
    """Bookkeeping for one round-trip, kept out of the main loop's way."""

    number: int
    messages: list[Message] = field(default_factory=list)


class DeckGenerationService:
    def __init__(self,
                 chat: ChatClient,
                 validator: DeckValidator,
                 prompts: PromptBuilder | None = None,
                 ids: DeckIdFactory | None = None,
                 topics: TopicResolver | None = None,
                 verbatim: VerbatimOverlapDetector | None = None,
                 lengths: LengthTargetAdvisor | None = None,
                 json_extractor: JsonExtractor | None = None,
                 max_attempts: int = DEFAULT_MAX_ATTEMPTS):
        self._chat = chat
        self._validator = validator
        self._prompts = prompts or PromptBuilder()
        self._ids = ids or DeckIdFactory()
        self._topics = topics or TopicResolver()
        self._verbatim = verbatim or VerbatimOverlapDetector()
        self._lengths = lengths or LengthTargetAdvisor()
        self._json = json_extractor or JsonExtractor()
        self._max_attempts = max_attempts

    def generate(self, request: GenerationRequest,
                 reporter: ProgressReporter | None = None) -> Deck:
        report = resolve(reporter)
        topic = self._topics.resolve(request.topic, request.source)
        deck_id = self._ids.create(topic, request.slug)
        source_text = request.source_text

        messages = self._prompts.opening(topic, request.archetype, request.palette,
                                         request.notes, request.source, request.framework)
        problems: list[str] = []

        for attempt in range(1, self._max_attempts + 1):
            raw = self._chat.complete(messages)

            try:
                payload = self._json.extract(raw)
            except (ValueError, json.JSONDecodeError) as exc:
                messages += self._prompts.unparseable(raw, str(exc))
                report.emit(f"  attempt {attempt}: unparseable output, retrying")
                continue

            deck = self._assemble(deck_id, topic, request, payload)
            problems = self._critique(deck, source_text, attempt, report)

            if not problems:
                report.emit(f"  ✓ valid on attempt {attempt}"
                            + (" (original wording confirmed)" if source_text else ""))
                return deck

            messages += self._prompts.rejection(raw, problems + self._lengths.targets(deck))

        raise GenerationError(f"still invalid after {self._max_attempts} attempts: "
                              + "; ".join(problems))

    # -- steps --------------------------------------------------------------

    def _assemble(self, deck_id: str, topic: str,
                  request: GenerationRequest, payload: dict) -> Deck:
        """Model copy plus code-owned identity. The model never sets these fields."""
        deck = Deck.from_dict({
            "id": deck_id,
            "archetype": request.archetype,
            "palette": request.palette,
            "topic": topic,
            "pillar": request.pillar or "",
            "cta_target": "wearezylo.com",
            "slides": payload.get("slides", []),
            "caption": payload.get("caption", ""),
            "hashtags": payload.get("hashtags", []),
        })
        if request.framework and request.framework != AUTO:
            deck.framework = request.framework
        if request.source and request.source.url:
            # Provenance only; never rendered on a slide.
            deck.source_url = request.source.url
        return deck

    def _critique(self, deck: Deck, source_text: str, attempt: int,
                  report: ProgressReporter) -> list[str]:
        """Validation errors plus copied wording — one combined rejection list."""
        result = self._validator.validate(deck)
        for message in result.warnings:
            report.emit(f"  WARN  {message}")

        copied = self._verbatim.hits(deck, source_text) if source_text else []
        if copied:
            report.emit(f"  attempt {attempt}: {len(copied)} passage(s) copied from the source")

        problems = result.errors + copied
        if problems and not copied:
            report.emit(f"  attempt {attempt}: {len(problems)} validation error(s)")
        return problems


# -- convenience wrappers, used by tools/capture_baseline.py and the tests -----

def verbatim_hits(deck: Deck, source_text: str, n: int = 7) -> list[str]:
    return VerbatimOverlapDetector(n).hits(deck, source_text)


def length_targets(deck: Deck, margin: int = 25) -> list[str]:
    return LengthTargetAdvisor(margin).targets(deck)


def as_messages(messages: Sequence[Message]) -> list[dict]:
    return [m.to_dict() for m in messages]
