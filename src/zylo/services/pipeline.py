"""The end-to-end use case: read source -> generate -> validate -> save -> render.

The API and the CLI both call this, which is what keeps the browser UI and the
terminal honest about doing the same thing. Stage transitions are reported
separately from log lines because the web UI shows them differently: the stage
drives a progress indicator, the log lines scroll underneath it.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..config import Paths
from ..domain.deck import Deck
from ..domain.errors import GenerationError
from ..domain.source import SourceMaterial
from ..domain.validation import DeckValidator
from ..ports import DeckRepository, SourceExtractor
from ..prompts.frameworks import AUTO
from ..reporting import ProgressReporter, resolve
from .generation import DeckGenerationService, GenerationRequest
from .rendering import DeckRenderingService


class Stage:
    QUEUED = "queued"
    READING = "reading"
    GENERATING = "generating"
    VALIDATING = "validating"
    RENDERING = "rendering"
    DONE = "done"
    FAILED = "failed"


@runtime_checkable
class PipelineObserver(Protocol):
    """Watches a run: coarse stage transitions plus fine-grained log lines."""

    def stage(self, name: str, deck_id: str | None = None) -> None:
        ...

    def emit(self, message: str) -> None:
        ...


class NullObserver:
    def stage(self, name: str, deck_id: str | None = None) -> None:
        return None

    def emit(self, message: str) -> None:
        return None


class ReporterObserver:
    """Wraps a plain reporter — log lines pass through, stages are dropped."""

    def __init__(self, reporter: ProgressReporter):
        self._reporter = resolve(reporter)

    def stage(self, name: str, deck_id: str | None = None) -> None:
        return None

    def emit(self, message: str) -> None:
        self._reporter.emit(message)


@dataclass(frozen=True)
class DeckBrief:
    """A full request for a deck, as the UI or CLI supplies it.

    Exactly one of topic / source_url / source_text has to carry enough to work
    with; the delivery layer checks that before this gets here.
    """

    topic: str | None = None
    archetype: str = "insight"
    palette: str = "dark"
    notes: str | None = None
    slug: str | None = None
    pillar: str | None = None
    framework: str = AUTO
    source_url: str | None = None
    source_text: str | None = None

    def generation_request(self, source: SourceMaterial | None) -> GenerationRequest:
        return GenerationRequest(
            topic=self.topic or "", archetype=self.archetype, palette=self.palette,
            slug=self.slug, pillar=self.pillar, notes=self.notes,
            framework=self.framework, source=source,
        )


@dataclass(frozen=True)
class PipelineResult:
    deck: Deck
    deck_file: Path
    slide_files: list[Path]


class DeckPipeline:
    def __init__(self,
                 generator: DeckGenerationService,
                 renderer: DeckRenderingService,
                 validator: DeckValidator,
                 repository: DeckRepository,
                 extractor: SourceExtractor,
                 paths: Paths):
        self._generator = generator
        self._renderer = renderer
        self._validator = validator
        self._repository = repository
        self._extractor = extractor
        self._paths = paths

    def run(self, brief: DeckBrief, observer: PipelineObserver | None = None) -> PipelineResult:
        watch = observer or NullObserver()
        reporter = _ObserverReporter(watch)

        source = self._read_source(brief, watch, reporter)

        watch.stage(Stage.GENERATING)
        watch.emit("Writing the deck"
                   + (" from the source points" if source else f" for: {brief.topic}"))
        deck = self._generator.generate(brief.generation_request(source), reporter)

        watch.stage(Stage.VALIDATING, deck.id)
        self._verify(deck, watch)

        deck_file = self._repository.save(deck)
        watch.emit(f"Wrote {self._paths.relative(deck_file)}")

        watch.stage(Stage.RENDERING)
        slide_files = self._renderer.render(deck, deck_file.parent, reporter)

        watch.stage(Stage.DONE)
        watch.emit("Deck ready for review")
        return PipelineResult(deck=deck, deck_file=deck_file, slide_files=slide_files)

    def rerender(self, deck_id: str, observer: PipelineObserver | None = None) -> list[Path]:
        """Re-render an existing deck after a hand edit to its deck.json."""
        watch = observer or NullObserver()
        directory = self._repository.resolve_directory(deck_id)
        watch.stage(Stage.RENDERING, deck_id)
        slide_files = self._renderer.render_file(directory / "deck.json", _ObserverReporter(watch))
        watch.stage(Stage.DONE, deck_id)
        return slide_files

    # -- steps --------------------------------------------------------------

    def _read_source(self, brief: DeckBrief, watch: PipelineObserver,
                     reporter: ProgressReporter) -> SourceMaterial | None:
        if brief.source_url:
            watch.stage(Stage.READING)
            watch.emit(f"Reading {brief.source_url}")
            return self._extractor.extract(brief.source_url, reporter)
        if brief.source_text:
            watch.stage(Stage.READING)
            source = SourceMaterial.from_text(brief.source_text)
            watch.emit(f"Using {len(source.text)} characters of pasted source text")
            return source
        return None

    def _verify(self, deck: Deck, watch: PipelineObserver) -> None:
        """The generator already validated; re-running here is the guarantee that
        what was saved is what was checked."""
        result = self._validator.validate(deck)
        for message in result.warnings:
            watch.emit(f"WARN {message}")
        if not result.ok:
            raise GenerationError(result.joined_errors())
        watch.emit("Validation passed")


class _ObserverReporter:
    """Lets services that only know about `ProgressReporter` feed an observer."""

    def __init__(self, observer: PipelineObserver):
        self._observer = observer

    def emit(self, message: str) -> None:
        self._observer.emit(message)
