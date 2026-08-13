"""Routers, each built by a factory that takes the container.

Passing the container in rather than reaching for a module-level global is what
lets a test spin up an app wired to fakes.
"""
from .decks import build_deck_router
from .jobs import build_job_router
from .meta import build_meta_router

__all__ = ["build_deck_router", "build_job_router", "build_meta_router"]
