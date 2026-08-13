"""Text helpers shared by validation, generation and rendering.

`**highlight**` markers are authoring syntax, not content: they render as an
accent span and are excluded from every character count. Keeping that rule in
one place is what stops the validator and the renderer from disagreeing about
how long a field is.
"""
import re

HIGHLIGHT_RE = re.compile(r"\*\*(.+?)\*\*")
_MARKER = "**"


def strip_markers(value) -> str:
    """The text as the reader sees it — highlight markers removed."""
    return str(value).replace(_MARKER, "")


def visible_length(value) -> int:
    """Character count the limits are enforced against."""
    return len(strip_markers(value))


def markers_balanced(value) -> bool:
    return str(value).count(_MARKER) % 2 == 0


def words(value) -> list[str]:
    """Lowercased alphanumeric words — the unit the verbatim check compares."""
    return re.findall(r"[a-z0-9]+", str(value).lower())
