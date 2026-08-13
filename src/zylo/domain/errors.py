"""The error vocabulary. One base class so delivery layers can catch broadly.

Each layer raises its own subclass, and every message is written to be shown
straight to a non-technical operator — the web UI prints them verbatim.
"""


class ZyloError(RuntimeError):
    """Base for every expected failure. Unexpected ones stay as-is and surface loudly."""


class MalformedDeckError(ZyloError):
    """Deck JSON that is not even shaped like a deck (not an object, unreadable)."""


class ExtractError(ZyloError):
    """A URL could not be turned into usable text."""


class GenerationError(ZyloError):
    """The model could not produce a valid deck."""


class RenderError(ZyloError):
    """A deck could not be rendered to PNGs."""


class DeckNotFoundError(ZyloError):
    """No deck with that id exists in the repository."""
