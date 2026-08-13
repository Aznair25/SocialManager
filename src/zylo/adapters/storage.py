"""Decks on disk.

Layout, unchanged from before the refactor:

    decks/<deck-id>/deck.json
                   /slides/NN.png
                   /contact-sheet.png
                   /caption.txt

`DeckArtifacts` exists so the API can ask "is this rendered?" or "where is slide
03?" without assembling paths itself — path traversal is checked in one place.
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from ..domain.deck import Deck
from ..domain.errors import DeckNotFoundError, MalformedDeckError


@dataclass(frozen=True)
class DeckArtifacts:
    """Everything a rendered deck leaves behind, addressed safely."""

    directory: Path

    @property
    def deck_file(self) -> Path:
        return self.directory / "deck.json"

    @property
    def slides_dir(self) -> Path:
        return self.directory / "slides"

    @property
    def contact_sheet(self) -> Path:
        return self.directory / "contact-sheet.png"

    @property
    def caption_file(self) -> Path:
        return self.directory / "caption.txt"

    @property
    def is_rendered(self) -> bool:
        return self.contact_sheet.is_file()

    def slide_names(self) -> list[str]:
        if not self.slides_dir.is_dir():
            return []
        return sorted(p.name for p in self.slides_dir.glob("*.png"))

    def slide_path(self, name: str) -> Path:
        """Resolve a slide by filename, refusing anything outside slides/."""
        path = (self.slides_dir / name).resolve()
        if path.parent != self.slides_dir.resolve() or not path.is_file():
            raise DeckNotFoundError("slide not found")
        return path

    def caption(self) -> str:
        return self.caption_file.read_text(encoding="utf-8") if self.caption_file.is_file() else ""

    def files(self) -> Iterator[Path]:
        """Every file under the deck directory, for the download zip."""
        return (p for p in sorted(self.directory.rglob("*")) if p.is_file())


class FileSystemDeckRepository:
    """Reads and writes decks under a root directory. Implements `DeckRepository`."""

    def __init__(self, root: Path):
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    # -- addressing ---------------------------------------------------------

    def directory(self, deck_id: str) -> Path:
        return self._root / deck_id

    def deck_file(self, deck_id: str) -> Path:
        return self.directory(deck_id) / "deck.json"

    def resolve_directory(self, deck_id: str) -> Path:
        """Directory for an existing deck, refusing ids that escape the root.

        `deck_id` reaches this from an HTTP path segment, so "../../etc" has to
        fail here rather than anywhere further in.
        """
        path = self.directory(deck_id).resolve()
        if path.parent != self._root.resolve() or not path.is_dir():
            raise DeckNotFoundError(f"deck '{deck_id}' not found")
        return path

    def artifacts(self, deck_id: str) -> DeckArtifacts:
        return DeckArtifacts(self.resolve_directory(deck_id))

    def exists(self, deck_id: str) -> bool:
        try:
            self.resolve_directory(deck_id)
        except DeckNotFoundError:
            return False
        return True

    # -- reading and writing ------------------------------------------------

    def save(self, deck: Deck) -> Path:
        target = self.deck_file(deck.id)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(deck.to_dict(), ensure_ascii=False, indent=2) + "\n"
        target.write_text(payload, encoding="utf-8")
        return target

    def load(self, deck_id: str) -> Deck:
        return self.load_from(self.resolve_directory(deck_id) / "deck.json")

    def load_from(self, deck_file: Path) -> Deck:
        deck_file = Path(deck_file)
        if not deck_file.is_file():
            raise DeckNotFoundError(f"no deck.json at {deck_file}")
        try:
            data = json.loads(deck_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MalformedDeckError(f"{deck_file.name} is not valid JSON: {exc}") from exc
        return Deck.from_dict(data)

    def list_ids(self) -> list[str]:
        """Newest first — ids start with an ISO date, so reverse name order is date order."""
        if not self._root.is_dir():
            return []
        return [d.name for d in sorted(self._root.iterdir(), reverse=True)
                if (d / "deck.json").is_file()]

    def load_all(self) -> Iterator[tuple[str, Deck]]:
        """Every readable deck. Unparseable ones are skipped, not fatal — one bad
        directory must not take down the whole listing."""
        for deck_id in self.list_ids():
            try:
                yield deck_id, self.load_from(self.deck_file(deck_id))
            except (MalformedDeckError, DeckNotFoundError):
                continue
