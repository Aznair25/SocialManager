#!/usr/bin/env python3
"""Compatibility shim — the implementation lives in src/zylo/prompts/.

Kept so existing imports (`from frameworks import choices, framework_block`)
keep working. New code should use `zylo.prompts.FrameworkCatalog`, which offers
the same behaviour as methods rather than module functions.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from zylo.prompts.frameworks import DEFAULT_FRAMEWORKS, FrameworkCatalog  # noqa: E402
from zylo.prompts.voice import HOOKS, PSYCHOLOGY  # noqa: E402

_CATALOG = FrameworkCatalog.default()

#: framework -> (archetypes it suits, prompt block)
FRAMEWORKS = {f.name: (f.archetypes, f.guidance) for f in DEFAULT_FRAMEWORKS}


def framework_block(framework, archetype):
    return _CATALOG.prompt_block(framework, archetype)


def choices():
    return _CATALOG.choices()


def for_archetype(archetype):
    return _CATALOG.choices_for(archetype)


__all__ = ["FRAMEWORKS", "HOOKS", "PSYCHOLOGY", "choices", "for_archetype", "framework_block"]
