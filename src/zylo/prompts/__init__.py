"""Prompt vocabulary and assembly.

The text lives here as data; `PromptBuilder` is the only thing that decides how
it is stitched together. Editing Zylo's voice therefore never means touching the
generation service.
"""
from .builder import PromptBuilder
from .frameworks import Framework, FrameworkCatalog
from .voice import ARCHETYPE_GUIDE, ENGAGEMENT, HOOKS, PSYCHOLOGY, SOURCE_RULES, VOICE, ZYLO

__all__ = [
    "ARCHETYPE_GUIDE",
    "ENGAGEMENT",
    "Framework",
    "FrameworkCatalog",
    "HOOKS",
    "PSYCHOLOGY",
    "PromptBuilder",
    "SOURCE_RULES",
    "VOICE",
    "ZYLO",
]
