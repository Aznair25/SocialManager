"""Assembles the messages sent to the model.

One class owns the whole conversation shape — system prompt, the opening user
turn, and the correction turn after a rejection. The generation service decides
*when* to say something; this decides *what* is said. Keeping the two apart is
what lets the retry loop be tested without a word of prompt text in the test.
"""
import json
from dataclasses import dataclass
from typing import Sequence

from ..domain.source import SourceMaterial
from ..domain.validation import limits_as_prompt_data
from .frameworks import AUTO, FrameworkCatalog
from .voice import ARCHETYPE_GUIDE, ENGAGEMENT, SOURCE_RULES, VOICE, ZYLO


@dataclass(frozen=True)
class Message:
    """One chat turn. Converted to the provider's shape by the adapter."""

    role: str
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


def as_dicts(messages: Sequence[Message]) -> list[dict]:
    return [m.to_dict() for m in messages]


class PromptBuilder:
    def __init__(self, catalog: FrameworkCatalog | None = None):
        self._catalog = catalog or FrameworkCatalog.default()

    # -- system -------------------------------------------------------------

    def system_prompt(self, archetype: str, framework: str = AUTO) -> str:
        return (
            ZYLO + "\n\n"
            + ENGAGEMENT + "\n\n"
            + VOICE + "\n\n"
            "Archetype '" + archetype + "' decides how slides LOOK: " + ARCHETYPE_GUIDE[archetype] + "\n\n"
            "The framework decides how the deck ARGUES.\n"
            + self._catalog.prompt_block(framework, archetype) + "\n\n"
            "HARD character limits per field (counted after removing ** markers) — exceeding any limit is a failure:\n"
            + json.dumps(limits_as_prompt_data(), indent=2) + "\n"
            "These are CHARACTERS, not words — letters, spaces and punctuation all count. Models "
            "routinely overshoot these, so write to roughly 85% of each limit and leave yourself margin: "
            "aim for ~170 characters on a 200 limit, ~38 on a 44 limit. Count each field before you "
            "answer. One tight sentence beats two padded ones; if a body needs a second clause to make "
            "sense, cut the idea down instead of stretching the box.\n\n"
            "Emphasis: you MAY wrap one key phrase in the cover hook with **double asterisks** (renders as accent color). "
            "Use at most one highlight in the whole deck.\n\n"
            "The cta slide: field 'line' (a calm closing question or statement, <=60 chars). Do not add a button field. "
            "The cta slide shows only the line and the button — no URL or email is rendered, and the "
            "caption carries the link instead. Never put a URL or an email address in 'line'.\n\n"
            "Caption: 1 hook line, blank line, 2-3 short lines expanding the promise, blank line, "
            "one CTA line ending with 'wearezylo.com'. No emojis in the caption either.\n"
            "Hashtags: 5-10 strings, no '#' prefix, mixing niche and reach (e.g. AIConsulting, EnterpriseAI).\n\n"
            "Return ONLY a JSON object, no markdown fences, no commentary, with exactly these keys:\n"
            '{ "slides": [ {"role": "cover", ...}, ... ], "caption": "...", "hashtags": ["..."] }'
        )

    # -- user turns ---------------------------------------------------------

    def source_block(self, source: SourceMaterial) -> str:
        head = f"Title: {source.title}\n" if source.title else ""
        return f"{SOURCE_RULES}\n\n{head}<<<SOURCE\n{source.text.strip()}\nSOURCE>>>"

    def brief(self, topic: str, palette: str, notes: str | None = None,
              source: SourceMaterial | None = None) -> str:
        message = f"Topic: {topic}\nPalette: {palette} (affects tone of visuals only, not copy)."
        if notes:
            message += f"\nDirection notes: {notes}"
        if source and source.text:
            message += "\n\n" + self.source_block(source)
        return message

    def opening(self, topic: str, archetype: str, palette: str, notes: str | None = None,
                source: SourceMaterial | None = None, framework: str = AUTO) -> list[Message]:
        return [
            Message("system", self.system_prompt(archetype, framework)),
            Message("user", self.brief(topic, palette, notes, source)),
        ]

    # -- correction turns ---------------------------------------------------

    def unparseable(self, raw: str, reason: str) -> list[Message]:
        return [
            Message("assistant", raw),
            Message("user", f"Output was not parseable JSON ({reason}). "
                            f"Return the full corrected JSON object only."),
        ]

    def rejection(self, raw: str, problems: Sequence[str]) -> list[Message]:
        return [
            Message("assistant", raw),
            Message("user",
                    "Rejected:\n- " + "\n- ".join(problems)
                    + "\n\nFix every issue listed. Where a target length is given, hit it by "
                      "deleting words — cut a clause or an example, do not reword at the same "
                      "length. Leave every field that was not listed exactly as it is. Return the "
                      "full corrected JSON object only."),
        ]
