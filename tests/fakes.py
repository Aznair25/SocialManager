"""Stand-ins for the three things the pipeline cannot do in a test: call a model,
drive a browser, fetch a page.

Each implements the matching Protocol in zylo/ports.py, which is the whole point
of those Protocols existing.
"""
import json
from contextlib import contextmanager
from pathlib import Path

from zylo.adapters.browser import RawPage

# A 1x1 PNG. The contact sheet base64-encodes whatever the slide files contain,
# so they only have to be readable bytes.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
    "de0000000c4944415408d763f8cfc00000030101002d0dd40000000049454e44ae426082"
)


class FakeChatClient:
    """Replays canned replies and records what it was asked."""

    def __init__(self, replies):
        self.replies = [r if isinstance(r, str) else json.dumps(r) for r in replies]
        self.calls: list[list] = []

    def complete(self, messages):
        self.calls.append(list(messages))
        if not self.replies:
            raise AssertionError("FakeChatClient ran out of replies")
        return self.replies.pop(0)

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def last_user_message(self) -> str:
        return self.calls[-1][-1].content


class FakeScreenshotSession:
    def __init__(self, log: list, width: int, height: int):
        self.log = log
        self.width, self.height = width, height

    def resize(self, width: int, height: int) -> None:
        self.width, self.height = width, height
        self.log.append(("resize", width, height))

    def capture(self, html: str, path: Path, full_page: bool = False, settle_ms: int = 120) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(TINY_PNG)
        self.log.append(("capture", path.name, len(html), full_page, self.width, self.height))
        return path


class FakeScreenshotEngine:
    """Writes real (tiny) PNGs so downstream steps that read them still work."""

    def __init__(self):
        self.log: list = []
        self.sessions = 0

    @contextmanager
    def session(self, width: int, height: int):
        self.sessions += 1
        self.log.append(("session", width, height))
        yield FakeScreenshotSession(self.log, width, height)
        self.log.append(("close",))

    def captured(self) -> list[str]:
        return [entry[1] for entry in self.log if entry[0] == "capture"]

    def html_sizes(self) -> list[int]:
        return [entry[2] for entry in self.log if entry[0] == "capture"]


class FakePageFetcher:
    """Returns a canned page, or raises whatever it was given."""

    def __init__(self, page: RawPage | None = None, error: Exception | None = None):
        self.page = page
        self.error = error
        self.requested: list[str] = []

    def fetch(self, url: str) -> RawPage:
        self.requested.append(url)
        if self.error:
            raise self.error
        return self.page


class RecordingReporter:
    def __init__(self):
        self.messages: list[str] = []

    def emit(self, message: str) -> None:
        self.messages.append(message)

    def text(self) -> str:
        return "\n".join(self.messages)


class RecordingObserver(RecordingReporter):
    def __init__(self):
        super().__init__()
        self.stages: list[str] = []
        self.deck_ids: list[str] = []

    def stage(self, name: str, deck_id: str | None = None) -> None:
        self.stages.append(name)
        if deck_id:
            self.deck_ids.append(deck_id)
