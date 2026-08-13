"""Filesystem layout and runtime settings, resolved once and passed down.

Nothing below this module reads `os.environ` or computes a path from
`__file__` — they take a `Settings` instead, which is what lets a test point the
whole application at a temporary directory.
"""
import os
from dataclasses import dataclass, replace
from pathlib import Path

DEFAULT_MODEL = "gpt-5.1"
DEFAULT_PORT = 8777
DEFAULT_HOST = "127.0.0.1"
DEFAULT_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Paths:
    """Where everything lives, relative to the project root."""

    root: Path

    @classmethod
    def discover(cls) -> "Paths":
        # src/zylo/config.py -> src/zylo -> src -> project root
        return cls(Path(__file__).resolve().parents[2])

    @property
    def decks(self) -> Path:
        return self.root / "decks"

    @property
    def brand(self) -> Path:
        return self.root / "brand"

    @property
    def fonts(self) -> Path:
        return self.brand / "fonts"

    @property
    def tokens_file(self) -> Path:
        return self.brand / "tokens.json"

    @property
    def templates(self) -> Path:
        return self.root / "templates"

    @property
    def base_css(self) -> Path:
        return self.templates / "base.css"

    @property
    def web(self) -> Path:
        return self.root / "web"

    @property
    def env_file(self) -> Path:
        return self.root / ".env"

    def relative(self, path: Path) -> str:
        """For log lines: project-relative when possible, absolute otherwise."""
        path = Path(path)
        try:
            return str(path.resolve().relative_to(self.root.resolve()))
        except ValueError:
            return str(path)


class EnvFile:
    """Loads `.env` with setdefault semantics — a real environment variable wins."""

    def __init__(self, path: Path):
        self._path = Path(path)

    def load(self, environ: dict | None = None) -> int:
        env = os.environ if environ is None else environ
        if not self._path.exists():
            return 0
        loaded = 0
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env.setdefault(key.strip(), value.strip())
            loaded += 1
        return loaded


@dataclass(frozen=True)
class Settings:
    paths: Paths
    model: str = DEFAULT_MODEL
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    max_attempts: int = DEFAULT_MAX_ATTEMPTS

    @classmethod
    def from_env(cls, paths: Paths | None = None, load_dotenv: bool = True) -> "Settings":
        paths = paths or Paths.discover()
        if load_dotenv:
            EnvFile(paths.env_file).load()
        return cls(
            paths=paths,
            model=os.environ.get("ZYLO_MODEL", DEFAULT_MODEL),
            port=int(os.environ.get("ZYLO_PORT", DEFAULT_PORT)),
        )

    @property
    def api_key(self) -> str:
        return os.environ.get("OPENAI_API_KEY", "")

    @property
    def api_key_set(self) -> bool:
        return bool(self.api_key)

    def with_(self, **changes) -> "Settings":
        return replace(self, **changes)
