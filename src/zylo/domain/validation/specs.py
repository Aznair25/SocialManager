"""Per-role field specs — the hard limits from schema/deck.schema.json.

Character limits are counted after `**` markers are stripped. They exist because
the templates have fixed type sizes: copy that does not fit gets rewritten, the
type never shrinks (AGENT.md rule 3).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SlideSpec:
    """What one slide role requires and how long each of its fields may be."""

    role: str
    required: tuple[str, ...]
    limits: dict  # field name -> max visible characters

    def limit_for(self, field: str) -> int | None:
        return self.limits.get(field)


# hook is capped hard at 55: the cover is a scroll-stopper, not a summary.
SLIDE_SPECS: dict[str, SlideSpec] = {
    "cover": SlideSpec("cover", ("hook",), {"hook": 55, "kicker": 24}),
    "stat": SlideSpec("stat", ("value", "label"),
                      {"value": 8, "label": 60, "context": 110, "kicker": 24}),
    "content": SlideSpec("content", ("title", "body"),
                         {"kicker": 24, "title": 44, "body": 200}),
    "mythfact": SlideSpec("mythfact", ("myth", "fact"), {"myth": 90, "fact": 160}),
    "cta": SlideSpec("cta", ("line",), {"line": 60, "button": 24}),
}

#: Which roles may appear between cover and cta, per archetype.
MIDDLE_ROLES: dict[str, tuple[str, ...]] = {
    "stat": ("stat", "content"),
    "insight": ("content",),
    "mythfact": ("mythfact", "content"),
}

#: A stat value longer than this still renders, but at a reduced size.
STAT_VALUE_COMFORTABLE = 6

MIN_SLIDES = 5
MAX_SLIDES = 20          # Instagram's hard cap
RECOMMENDED_MAX_SLIDES = 10
MAX_CAPTION_CHARS = 2200  # Instagram's hard cap
MIN_HASHTAGS = 5
MAX_HASHTAGS = 10
HASHTAG_HARD_CAP = 30


def spec_for(role: str) -> SlideSpec | None:
    return SLIDE_SPECS.get(role)


def limits_as_prompt_data() -> dict:
    """The shape the prompt shows the model: {role: {field: max}}."""
    return {role: dict(spec.limits) for role, spec in SLIDE_SPECS.items()}
