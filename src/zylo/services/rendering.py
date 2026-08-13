"""deck.json -> slide PNGs + contact sheet + caption.txt.

Validation runs first and refuses to render a deck with errors. That is
deliberate: a rendered PNG is what gets uploaded, so an invalid deck must never
reach a file a human could mistake for finished work.
"""
from pathlib import Path
from typing import Sequence

from ..config import Paths
from ..domain.deck import Deck
from ..domain.errors import RenderError
from ..domain.validation import DeckValidator
from ..ports import DeckRepository, ScreenshotEngine
from ..rendering.contact_sheet import ContactSheetHtmlBuilder
from ..rendering.slides import SlideHtmlBuilder
from ..rendering.theme import Theme
from ..reporting import ProgressReporter, resolve

SLIDE_SETTLE_MS = 120
SHEET_SETTLE_MS = 300  # let the inlined thumbnails decode


class CaptionWriter:
    """caption.txt — the caption plus hashtags, ready to paste into Instagram."""

    def render(self, deck: Deck) -> str:
        tags = " ".join(t if str(t).startswith("#") else "#" + str(t) for t in deck.hashtags)
        return deck.caption.strip() + "\n\n" + tags + "\n"

    def write(self, deck: Deck, directory: Path) -> Path:
        target = Path(directory) / "caption.txt"
        target.write_text(self.render(deck), encoding="utf-8")
        return target


class DeckRenderingService:
    def __init__(self,
                 engine: ScreenshotEngine,
                 validator: DeckValidator,
                 slides: SlideHtmlBuilder,
                 contact_sheet: ContactSheetHtmlBuilder,
                 theme: Theme,
                 repository: DeckRepository,
                 paths: Paths,
                 captions: CaptionWriter | None = None):
        self._engine = engine
        self._validator = validator
        self._slides = slides
        self._sheet = contact_sheet
        self._theme = theme
        self._repository = repository
        self._paths = paths
        self._captions = captions or CaptionWriter()

    def render_file(self, deck_file: Path, reporter: ProgressReporter | None = None) -> list[Path]:
        """Render the deck.json at `deck_file`, writing artefacts beside it."""
        deck_file = Path(deck_file).resolve()
        return self.render(self._repository.load_from(deck_file), deck_file.parent, reporter)

    def render(self, deck: Deck, directory: Path,
               reporter: ProgressReporter | None = None) -> list[Path]:
        report = resolve(reporter)
        self._guard(deck, report)

        directory = Path(directory)
        slides_dir = directory / "slides"
        slides_dir.mkdir(parents=True, exist_ok=True)

        with self._engine.session(self._theme.width, self._theme.height) as session:
            pngs = self._capture_slides(deck, slides_dir, session, report)
            self._capture_contact_sheet(deck, directory, pngs, session, report)

        self._captions.write(deck, directory)
        report.emit("  ✓ caption.txt")
        report.emit(f"\n✓ {deck.id}: {len(pngs)} slides rendered "
                    f"to {self._paths.relative(slides_dir)}")
        return pngs

    # -- steps --------------------------------------------------------------

    def _guard(self, deck: Deck, report: ProgressReporter) -> None:
        result = self._validator.validate(deck)
        for message in result.warnings:
            report.emit(f"  WARN  {message}")
        if not result.ok:
            for message in result.errors:
                report.emit(f"  ERROR {message}")
            raise RenderError("validation failed — not rendering: " + result.joined_errors())

    def _capture_slides(self, deck: Deck, slides_dir: Path, session,
                        report: ProgressReporter) -> list[Path]:
        total = deck.slide_count
        pngs = []
        for i, slide in enumerate(deck.slides):
            target = slides_dir / ("%02d.png" % (i + 1))
            session.capture(self._slides.build(deck, slide, i, total), target,
                            settle_ms=SLIDE_SETTLE_MS)
            pngs.append(target)
            report.emit(f"  ✓ slide {i + 1}/{total} ({slide.role})")
        return pngs

    def _capture_contact_sheet(self, deck: Deck, directory: Path, pngs: Sequence[Path],
                               session, report: ProgressReporter) -> Path:
        html, width, height = self._sheet.build(deck, pngs)
        session.resize(width, height)
        target = directory / "contact-sheet.png"
        session.capture(html, target, full_page=True, settle_ms=SHEET_SETTLE_MS)
        report.emit("  ✓ contact-sheet.png")
        return target
