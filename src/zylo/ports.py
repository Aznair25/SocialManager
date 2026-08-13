"""The seams.

Every dependency on the outside world — the model, the browser, the disk —
enters through a Protocol declared here. Services depend on these; only
`container.py` knows which concrete adapter is plugged in.

The protocols are deliberately narrow: `ChatClient` has one method because one
method is all the generation service needs. A wider interface would force the
test fakes to implement things nothing calls.
"""
from pathlib import Path
from typing import ContextManager, Iterable, Protocol, Sequence, runtime_checkable

from .domain.deck import Deck
from .domain.source import SourceMaterial
from .prompts.builder import Message


@runtime_checkable
class ChatClient(Protocol):
    """A single-shot chat completion returning raw text."""

    def complete(self, messages: Sequence[Message]) -> str:
        ...


@runtime_checkable
class SourceExtractor(Protocol):
    """Turns a URL into reference material, or raises ExtractError explaining why not."""

    def extract(self, url: str, reporter=None) -> SourceMaterial:
        ...


@runtime_checkable
class ScreenshotSession(Protocol):
    """A live page that HTML can be pushed into and captured from."""

    def resize(self, width: int, height: int) -> None:
        ...

    def capture(self, html: str, path: Path, full_page: bool = False, settle_ms: int = 120) -> Path:
        ...


@runtime_checkable
class ScreenshotEngine(Protocol):
    def session(self, width: int, height: int) -> ContextManager[ScreenshotSession]:
        ...


@runtime_checkable
class DeckRepository(Protocol):
    """Persistence for decks and their rendered artefacts."""

    def save(self, deck: Deck) -> Path:
        ...

    def load(self, deck_id: str) -> Deck:
        ...

    def load_from(self, deck_file: Path) -> Deck:
        ...

    def exists(self, deck_id: str) -> bool:
        ...

    def directory(self, deck_id: str) -> Path:
        ...

    def deck_file(self, deck_id: str) -> Path:
        ...

    def list_ids(self) -> Iterable[str]:
        ...
