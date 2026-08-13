"""The FastAPI application factory.

`create_app(container)` rather than a module-level `app`: the container carries
every dependency, so a test can build an app backed by fakes and a temporary
deck directory without patching anything.

End to end: topic -> generate (OpenAI) -> validate -> render -> PNGs.
Non-technical users get the browser UI at /; everything it does is also a plain
REST call, so the same endpoints work from curl or another service.
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ..container import ApplicationContainer
from ..domain.errors import DeckNotFoundError, ZyloError
from .routers import build_deck_router, build_job_router, build_meta_router

TITLE = "Zylo Deck Studio"
VERSION = "2.0"


def create_app(container: ApplicationContainer | None = None) -> FastAPI:
    container = container or ApplicationContainer.default()
    app = FastAPI(title=TITLE, version=VERSION)
    app.state.container = container

    app.include_router(build_deck_router(container))
    app.include_router(build_job_router(container))
    app.include_router(build_meta_router(container))

    @app.exception_handler(DeckNotFoundError)
    def _not_found(_request, exc: DeckNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ZyloError)
    def _bad_request(_request, exc: ZyloError):
        # Every ZyloError message is written to be shown to an operator as-is.
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return app
