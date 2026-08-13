"""The deck model — the one shape every layer agrees on.

`Deck.from_dict` / `to_dict` round-trip decks/<id>/deck.json exactly, including
keys this code does not know about, so an older deck on disk survives a load and
save without silently losing fields.

Archetype and palette are held as plain strings rather than enums on purpose: an
invalid value has to be *representable* for the validator to be able to report
it. The enums below are for the API and CLI, where choices are constrained up
front.
"""
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .errors import MalformedDeckError
from .text import strip_markers


class Archetype(str, Enum):
    """How slides LOOK — which template renders them."""

    STAT = "stat"
    INSIGHT = "insight"
    MYTHFACT = "mythfact"

    @classmethod
    def values(cls) -> list[str]:
        return sorted(a.value for a in cls)


class Palette(str, Enum):
    DARK = "dark"
    LIGHT = "light"

    @classmethod
    def values(cls) -> list[str]:
        return [p.value for p in cls]


class SlideRole(str, Enum):
    COVER = "cover"
    STAT = "stat"
    CONTENT = "content"
    MYTHFACT = "mythfact"
    CTA = "cta"

    @classmethod
    def values(cls) -> list[str]:
        return [r.value for r in cls]


@dataclass(frozen=True)
class Slide:
    """One slide: a role plus whatever fields that role carries.

    Fields are kept as an open mapping rather than a field per role. Roles have
    disjoint field sets (a stat has value/label, a mythfact has myth/fact), so a
    single class with every field would be mostly empty on every instance, and a
    class per role would need a factory in three places to gain nothing — the
    validator already owns the per-role rules.
    """

    role: str
    fields: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data) -> "Slide":
        if not isinstance(data, Mapping):
            return cls(role="", fields={})
        return cls(role=data.get("role", ""),
                   fields={k: v for k, v in data.items() if k != "role"})

    def to_dict(self) -> dict:
        return {"role": self.role, **dict(self.fields)}

    def has(self, name: str) -> bool:
        return name in self.fields

    def raw(self, name: str, default: Any = "") -> Any:
        """The stored value, highlight markers intact."""
        return self.fields.get(name, default)

    def text(self, name: str, default: str = "") -> str:
        """The value as the reader sees it — markers stripped."""
        return strip_markers(self.fields.get(name, default))

    def is_blank(self, name: str) -> bool:
        return not str(self.fields.get(name) or "").strip()


# Written in this order so a regenerated deck.json diffs cleanly against an older one.
_CORE_KEYS = ("id", "archetype", "palette", "topic", "pillar", "cta_target",
              "slides", "caption", "hashtags")
_OPTIONAL_KEYS = ("framework", "source_url")


@dataclass
class Deck:
    """A full carousel spec. Identity fields are owned by code, copy by the model."""

    id: str
    archetype: str
    palette: str
    topic: str = ""
    pillar: str = ""
    cta_target: str = "wearezylo.com"
    slides: list[Slide] = field(default_factory=list)
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    framework: str | None = None
    source_url: str | None = None
    #: Keys present in the source JSON that this version does not model, preserved verbatim.
    extras: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data) -> "Deck":
        if not isinstance(data, Mapping):
            raise MalformedDeckError("deck.json is not an object")
        known = set(_CORE_KEYS) | set(_OPTIONAL_KEYS)
        return cls(
            id=data.get("id") or "",
            archetype=data.get("archetype") or "",
            palette=data.get("palette") or "",
            topic=data.get("topic") or "",
            pillar=data.get("pillar") or "",
            cta_target=data.get("cta_target") or "wearezylo.com",
            slides=[Slide.from_dict(s) for s in (data.get("slides") or [])],
            caption=data.get("caption") or "",
            hashtags=list(data.get("hashtags") or []),
            framework=data.get("framework"),
            source_url=data.get("source_url"),
            extras={k: v for k, v in data.items() if k not in known},
        )

    def to_dict(self) -> dict:
        out: dict = {
            "id": self.id,
            "archetype": self.archetype,
            "palette": self.palette,
            "topic": self.topic,
            "pillar": self.pillar,
            "cta_target": self.cta_target,
            "slides": [s.to_dict() for s in self.slides],
            "caption": self.caption,
            "hashtags": list(self.hashtags),
        }
        if self.framework:
            out["framework"] = self.framework
        if self.source_url:
            out["source_url"] = self.source_url
        out.update(self.extras)
        return out

    # -- shape questions the rules and renderer ask -------------------------

    @property
    def cover(self) -> Slide | None:
        return self.slides[0] if self.slides else None

    @property
    def closing(self) -> Slide | None:
        return self.slides[-1] if self.slides else None

    @property
    def middle(self) -> list[Slide]:
        """Slides between cover and cta — what a counted cover hook promises."""
        return self.slides[1:-1]

    @property
    def slide_count(self) -> int:
        return len(self.slides)

    def numbered(self):
        """(1-based index, slide) — validator messages are 1-based throughout."""
        return enumerate(self.slides, start=1)

    def slides_with_role(self, role: str) -> list[tuple[int, Slide]]:
        return [(i, s) for i, s in self.numbered() if s.role == role]
