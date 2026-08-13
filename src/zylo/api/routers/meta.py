"""Capabilities and the UI shell.

/api/config is what the browser form populates its dropdowns from, so adding a
framework or an archetype reaches the UI without a front-end change.
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from ...container import ApplicationContainer
from ...domain.deck import Archetype, Palette


def build_meta_router(container: ApplicationContainer) -> APIRouter:
    router = APIRouter(tags=["meta"])

    @router.get("/api/config")
    def config() -> dict:
        return {
            "archetypes": Archetype.values(),
            "palettes": Palette.values(),
            "frameworks": container.frameworks.choices(),
            "model": container.settings.model,
            "api_key_set": container.settings.api_key_set,
        }

    @router.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (container.paths.web / "index.html").read_text(encoding="utf-8")

    return router
