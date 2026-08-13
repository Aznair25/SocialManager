"""Access to templates/ — one HTML file per slide role, plus the shared stylesheet.

Templates are cached after first read: a deck renders 6-9 slides and most of
them share a role, so re-reading the same file per slide is pure waste.
"""
from pathlib import Path

from ..domain.errors import RenderError


class TemplateRepository:
    def __init__(self, templates_dir: Path):
        self._dir = Path(templates_dir)
        self._cache: dict[str, str] = {}

    def slide_template(self, role: str) -> str:
        if role not in self._cache:
            path = self._dir / f"{role}.html"
            if not path.is_file():
                raise RenderError(f"no template for slide role '{role}' (expected {path.name})")
            self._cache[role] = path.read_text(encoding="utf-8")
        return self._cache[role]

    def base_css(self) -> str:
        if "__base_css__" not in self._cache:
            path = self._dir / "base.css"
            if not path.is_file():
                raise RenderError(f"missing stylesheet: {path}")
            self._cache["__base_css__"] = path.read_text(encoding="utf-8")
        return self._cache["__base_css__"]
