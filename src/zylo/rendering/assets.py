"""Fonts and binary assets.

Both end up inlined because `set_content()` pages have an `about:blank` origin,
and Chromium refuses to load `file://` subresources from there — images come out
broken and webfonts silently fall back.
"""
import base64
from pathlib import Path


class AssetEncoder:
    """File to data URI."""

    @staticmethod
    def data_uri(path: Path, mime: str = "image/png") -> str:
        payload = base64.b64encode(Path(path).read_bytes()).decode("ascii")
        return f"data:{mime};base64,{payload}"

    @staticmethod
    def css_url(path: Path, mime: str = "image/png") -> str:
        return "url(%s)" % AssetEncoder.data_uri(path, mime)


class FontResolver:
    """Vendored Poppins if every weight is present, else Google Fonts at render time."""

    WEIGHTS = (300, 400, 500, 600)

    def __init__(self, font_dir: Path, weights: tuple[int, ...] = WEIGHTS):
        self._font_dir = Path(font_dir)
        self._weights = weights

    def _files(self) -> dict[int, Path]:
        return {w: self._font_dir / f"poppins-latin-{w}-normal.woff2" for w in self._weights}

    @property
    def is_vendored(self) -> bool:
        return all(p.exists() for p in self._files().values())

    def head_html(self) -> str:
        """The <head> fragment that makes Poppins available."""
        if self.is_vendored:
            faces = "".join(
                "@font-face{font-family:'Poppins';font-style:normal;font-weight:%d;"
                "src:url('file://%s') format('woff2');}" % (weight, path)
                for weight, path in self._files().items()
            )
            return "<style>%s</style>" % faces
        return (
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600&display=swap" rel="stylesheet">'
        )
