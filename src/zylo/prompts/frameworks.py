"""Narrative architectures — how a deck ARGUES.

`archetype` decides how a slide LOOKS (which template renders it). `framework`
decides why the reader keeps swiping. They are orthogonal: a stat deck can be a
Problem-Proof or a Value-Stack.

Adapted from the carousel frameworks in coreyhaines31/marketingskills
(skills/social/references/carousel-frameworks.md). The structures are kept; the
consumer/growth tone is not — everything here is re-pitched for AGENT.md rule 7
(enterprise-calm, no hype, no emojis, no exclamation marks) and for an executive
buyer rather than a founder audience.

Adding a framework means adding a `Framework` to `DEFAULT_FRAMEWORKS`; nothing
else in the codebase needs to change, and it appears in the CLI and API choices
automatically.
"""
from dataclasses import dataclass
from typing import Iterable

AUTO = "auto"


@dataclass(frozen=True)
class Framework:
    """A narrative structure plus the archetypes it reads well in."""

    name: str
    archetypes: tuple[str, ...]
    guidance: str

    def suits(self, archetype: str) -> bool:
        return archetype in self.archetypes


DEFAULT_FRAMEWORKS: tuple[Framework, ...] = (
    Framework(
        "problemproof",
        ("stat", "insight"),
        "FRAMEWORK: PROBLEM-PROOF. The deck opens with a claim and closes with the receipt; "
        "everything between explains the mechanism. The open loop is the engine — the reader swipes "
        "to find out whether the proof is real.\n"
        "- Cover: a specific claim, ideally carrying a number. A result, not advice.\n"
        "- Slide 2: reframe the problem. Name what is ACTUALLY going wrong, so the reader recognises "
        "their own organisation in it.\n"
        "- Middle slides: the mechanism. Named steps, named roles, named controls. Concrete beats vague.\n"
        "- Final content slide before the cta: the proof — the measurable outcome that closes the loop "
        "the cover opened.\n"
        "Failure mode: vague mechanism slides ('optimise your workflow'). If the middle does not name "
        "specifics, the proof reads as luck rather than a system. Use Zylo's real figures only "
        "(+85% operational efficiency, 3x faster deployment, -40% manual processes, 50+ companies); "
        "never invent a statistic.",
    ),
    Framework(
        "hacklist",
        ("insight", "stat"),
        "FRAMEWORK: HACK LIST. A contrarian opening, then numbered techniques that each re-earn the "
        "swipe on their own.\n"
        "- Cover: a claim implying most organisations get this wrong.\n"
        "- Slide 2: why the common approach fails.\n"
        "- Middle slides: one NAMED technique per slide. Naming is mandatory — 'the two-week rule' or "
        "'the reversibility test' travels and gets repeated; 'plan carefully' does not. Use the kicker "
        "for the number, the title for the name of the technique.\n"
        "- Close: one line of synthesis tying the techniques together, then the cta.\n"
        "Failure mode: techniques that are restatements of each other. Every slide must survive alone; "
        "if two collapse into one idea, merge them and ship a shorter deck.",
    ),
    Framework(
        "valuestack",
        ("insight", "stat"),
        "FRAMEWORK: VALUE-STACK. The cover makes a completeness promise with an exact count, and every "
        "swipe pays it down.\n"
        "- Cover: the exact count plus the exact deliverable — '[N] [things] that [outcome]'. The number "
        "MUST equal the number of slides between cover and cta. A count is a checkable promise.\n"
        "- Middle slides: one item per slide, no filler, same shape throughout.\n"
        "- Close: the cta.\n"
        "Failure mode: padding to reach a rounder number. A tight 5 beats a padded 8 — pick the count "
        "you can actually deliver, then deliver exactly it.",
    ),
    Framework(
        "callout",
        ("mythfact", "insight"),
        "FRAMEWORK: CALLOUT. A direct challenge to a common practice. Conviction, delivered calmly — "
        "this is a precise line drawn by a consultancy, never a rant. No sarcasm, no naming of "
        "companies or people.\n"
        "- Cover: the practice you are challenging, stated plainly enough to be disagreed with.\n"
        "- Middle slides: escalate with specifics — the actual meeting, the actual approval step, the "
        "actual cost. Show the failure; do not gesture at it.\n"
        "- Second-to-last content slide: THE FAIRNESS PIVOT. State what you are NOT attacking — "
        "'the problem is not X, it is Y'. This is what turns heat into a quotable line, and it "
        "pre-empts the obvious objection. Never skip it.\n"
        "Failure mode: skipping the pivot (reads as complaint), or attacking something Zylo itself "
        "does. Stay anti-practice, never anti-person.",
    ),
)


class UnknownFrameworkError(KeyError):
    """Asked for a framework that is not in the catalog."""


class FrameworkCatalog:
    """The set of frameworks available, and how they are offered to the model."""

    def __init__(self, frameworks: Iterable[Framework]):
        self._by_name = {f.name: f for f in frameworks}

    @classmethod
    def default(cls) -> "FrameworkCatalog":
        return cls(DEFAULT_FRAMEWORKS)

    def __contains__(self, name: object) -> bool:
        return name == AUTO or name in self._by_name

    def get(self, name: str) -> Framework:
        try:
            return self._by_name[name]
        except KeyError:
            raise UnknownFrameworkError(name) from None

    def names(self) -> list[str]:
        return sorted(self._by_name)

    def choices(self) -> list[str]:
        """Everything a caller may pass, `auto` first."""
        return [AUTO] + self.names()

    def choices_for(self, archetype: str) -> list[str]:
        return [AUTO] + sorted(f.name for f in self._by_name.values() if f.suits(archetype))

    def fitting(self, archetype: str) -> list[Framework]:
        """Catalog order, not alphabetical — the model reads these as a menu."""
        return [f for f in self._by_name.values() if f.suits(archetype)]

    def prompt_block(self, framework: str, archetype: str) -> str:
        """Prompt text for the chosen framework. 'auto' lets the model pick a fitting one."""
        if framework and framework != AUTO:
            return self.get(framework).guidance
        options = "\n\n".join(f"{f.name}\n{f.guidance}" for f in self.fitting(archetype))
        return (
            "Choose the narrative framework that best fits this material, then follow it for the whole "
            "deck. Do not blend two. Options:\n\n" + options
        )
