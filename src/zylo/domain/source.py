"""Reference material an operator supplied for a deck to be written from.

Deliberately not called a "document": the generator mines it for points and
writes every line fresh. Nothing here is ever copied through to a slide, and
`VerbatimOverlapDetector` enforces that.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceMaterial:
    """Text plus the provenance needed to record where it came from."""

    text: str
    url: str = ""
    title: str = ""

    @classmethod
    def from_text(cls, text: str) -> "SourceMaterial":
        """Pasted text, used when a site refuses to serve its article body."""
        return cls(text=(text or "").strip())

    @classmethod
    def from_dict(cls, data) -> "SourceMaterial | None":
        if not data:
            return None
        if isinstance(data, SourceMaterial):
            return data
        return cls(text=(data.get("text") or "").strip(),
                   url=data.get("url") or "",
                   title=data.get("title") or "")

    def to_dict(self) -> dict:
        return {"url": self.url, "title": self.title, "text": self.text}

    def __bool__(self) -> bool:
        return bool(self.text)

    @property
    def opening_sentence(self) -> str:
        """First substantial sentence — the topic fallback for pasted posts with no title."""
        import re

        first = next((line.strip() for line in self.text.splitlines() if len(line.strip()) > 25), "")
        return re.split(r"(?<=[.!?])\s", first)[0][:120].strip()
