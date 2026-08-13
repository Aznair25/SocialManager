"""Shared fixtures.

`container` is the interesting one: a real ApplicationContainer with the three
outside-world adapters replaced by fakes and the deck directory pointed at a
tmp_path. Everything else — validator, prompts, renderer, pipeline — is the real
object graph, so these are integration tests of the wiring, not mock theatre.
"""
import datetime

import pytest

from zylo.adapters.storage import FileSystemDeckRepository
from zylo.config import Paths, Settings
from zylo.container import ApplicationContainer
from zylo.domain.deck import Deck

from .fakes import FakeChatClient, FakePageFetcher, FakeScreenshotEngine

FIXED_DATE = datetime.date(2026, 8, 12)


@pytest.fixture
def project_paths() -> Paths:
    """The real project root — brand tokens and templates are read from it."""
    return Paths.discover()


@pytest.fixture
def settings(project_paths) -> Settings:
    return Settings(paths=project_paths, model="test-model")


@pytest.fixture
def deck_root(tmp_path):
    root = tmp_path / "decks"
    root.mkdir()
    return root


@pytest.fixture
def chat() -> FakeChatClient:
    return FakeChatClient([])


@pytest.fixture
def engine() -> FakeScreenshotEngine:
    return FakeScreenshotEngine()


@pytest.fixture
def fetcher() -> FakePageFetcher:
    return FakePageFetcher()


@pytest.fixture
def container(settings, deck_root, chat, engine, fetcher) -> ApplicationContainer:
    return ApplicationContainer(
        settings,
        chat_client=chat,
        screenshot_engine=engine,
        page_fetcher=fetcher,
        repository=FileSystemDeckRepository(deck_root),
    )


# -- deck builders ---------------------------------------------------------

def slide(role, **fields):
    return {"role": role, **fields}


def deck_payload(**overrides) -> dict:
    """A valid insight deck. Override any key to make it invalid on purpose."""
    payload = {
        "id": "2026-08-12_a-valid-deck",
        "archetype": "insight",
        "palette": "dark",
        "topic": "Adoption is the gap",
        "pillar": "",
        "cta_target": "wearezylo.com",
        "slides": [
            slide("cover", hook="Your pilot is not a strategy"),
            slide("content", title="Governance arrives late",
                  body="It lands after the build has already shipped."),
            slide("content", title="Capability stays outside",
                  body="The vendor keeps the knowledge when they leave."),
            slide("content", title="Licences are not usage",
                  body="Seats bought is not the same as work changed."),
            slide("cta", line="Where is your bottleneck?"),
        ],
        "caption": "Hook line\n\nBody line\n\nMore at wearezylo.com",
        "hashtags": ["AIConsulting", "EnterpriseAI", "AIGovernance",
                     "AIAdoption", "AIStrategy"],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def valid_deck() -> Deck:
    return Deck.from_dict(deck_payload())


@pytest.fixture
def model_reply() -> dict:
    """What the model returns: copy only, no identity fields."""
    payload = deck_payload()
    return {"slides": payload["slides"], "caption": payload["caption"],
            "hashtags": payload["hashtags"]}
