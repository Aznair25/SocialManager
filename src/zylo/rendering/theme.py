"""brand/tokens.json, and the CSS custom properties derived from it.

The design system has exactly two palettes. Rather than two token files, one set
of tokens carries both and `CssVariableBuilder` picks a side — so a colour is
defined once and the dark/light pairing is visible in a single place.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from ..domain.errors import RenderError
from .assets import AssetEncoder


@dataclass(frozen=True)
class Theme:
    """Parsed brand tokens plus the directory their assets are relative to."""

    tokens: dict
    brand_dir: Path

    @classmethod
    def load(cls, tokens_file: Path, brand_dir: Path | None = None) -> "Theme":
        tokens_file = Path(tokens_file)
        return cls(tokens=json.loads(tokens_file.read_text(encoding="utf-8")),
                   brand_dir=Path(brand_dir or tokens_file.parent))

    @property
    def color(self) -> dict:
        return self.tokens["color"]

    @property
    def identity(self) -> dict:
        return self.tokens["identity"]

    @property
    def canvas(self) -> dict:
        return self.tokens["canvas"]

    @property
    def radius(self) -> dict:
        return self.tokens["radius"]

    @property
    def width(self) -> int:
        return self.canvas["width"]

    @property
    def height(self) -> int:
        return self.canvas["height"]

    @property
    def padding(self) -> int:
        return self.canvas["pad"]

    @property
    def logo_path(self) -> Path:
        return self.brand_dir / self.identity["logo"]

    def logo_css_url(self) -> str:
        path = self.logo_path
        if not path.exists():
            raise RenderError(f"logo asset missing: {path}")
        return AssetEncoder.css_url(path)


class CssVariableBuilder:
    """Maps a palette name onto the `:root` custom properties the templates use."""

    def __init__(self, theme: Theme):
        self._theme = theme

    def variables(self, palette: str) -> dict:
        c = self._theme.color
        dark = palette == "dark"

        def pick(dark_key: str, light_key: str) -> str:
            return c[dark_key] if dark else c[light_key]

        return {
            "--bg": pick("bgDark", "bgLight"),
            "--fg": pick("fgOnDark", "fgOnLight"),
            "--soft": pick("fgSoftOnDark", "fgSoftOnLight"),
            "--muted": pick("fgMutedOnDark", "fgMutedOnLight"),
            "--numeral": pick("numeralOnDark", "numeralOnLight"),
            "--accent": c["accentPurple"],
            "--hl": c["accentLavender"] if dark else c["accentPurple"],
            "--chip-border": pick("borderOnDark", "borderOnLight"),
            "--chip-bg": pick("chipBgOnDark", "chipBgOnLight"),
            "--glow": c["glowPurple"],
            "--glow-2": c["glowLavender"],
            "--arc": pick("arcOnDark", "arcOnLight"),
            "--pill-bg": pick("fgOnDark", "fgOnLight"),
            "--pill-fg": pick("bgDark", "bgLight"),
            "--r-card": self._theme.radius["card"],
            "--r-pill": self._theme.radius["pill"],
            "--pad": "%dpx" % self._theme.padding,
            "--logo": self._theme.logo_css_url(),
        }

    def build(self, palette: str) -> str:
        return ":root{%s}" % ";".join("%s:%s" % kv for kv in self.variables(palette).items())
