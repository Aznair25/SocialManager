"""Deck endpoints: create, list, fetch, re-render, download.

Every handler is a translation — validate the request, call a service, shape the
response. Anything longer than a few lines belongs in a service instead.
"""
import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse

from ...container import ApplicationContainer
from ...domain.deck import Archetype, Palette
from ...domain.errors import DeckNotFoundError
from ..schemas import DeckRequest, deck_summary

MIN_TOPIC_CHARS = 3


def build_deck_router(container: ApplicationContainer) -> APIRouter:
    router = APIRouter(prefix="/api/decks", tags=["decks"])
    repository = container.repository

    def artifacts(deck_id: str):
        try:
            return repository.artifacts(deck_id)
        except DeckNotFoundError as exc:
            raise HTTPException(404, str(exc)) from None

    # -- create ------------------------------------------------------------

    @router.post("")
    def create_deck(request: DeckRequest) -> dict:
        """Kick off an end-to-end deck build. Returns immediately with a job id."""
        _reject_bad_request(request, container)

        brief = request.to_brief()
        job = container.jobs.create(topic=request.topic)
        container.job_runner.submit(job, lambda observer: container.pipeline.run(brief, observer))
        return {"job_id": job.id, "status": job.status}

    # -- read --------------------------------------------------------------

    @router.get("")
    def list_decks() -> dict:
        return {"decks": [
            deck_summary(deck_id, deck, repository.artifacts(deck_id).is_rendered)
            for deck_id, deck in repository.load_all()
        ]}

    @router.get("/{deck_id}")
    def get_deck(deck_id: str) -> dict:
        found = artifacts(deck_id)
        deck = repository.load_from(found.deck_file)
        return {"deck": deck.to_dict(), "slides": found.slide_names(),
                "caption": found.caption(), "contact_sheet": found.is_rendered}

    @router.get("/{deck_id}/slides/{name}")
    def get_slide(deck_id: str, name: str) -> FileResponse:
        try:
            path = artifacts(deck_id).slide_path(name)
        except DeckNotFoundError:
            raise HTTPException(404, "slide not found") from None
        return FileResponse(path, media_type="image/png")

    @router.get("/{deck_id}/contact-sheet.png")
    def get_contact_sheet(deck_id: str) -> FileResponse:
        path = artifacts(deck_id).contact_sheet
        if not path.is_file():
            raise HTTPException(404, "not rendered yet")
        return FileResponse(path, media_type="image/png")

    @router.get("/{deck_id}/caption.txt")
    def get_caption(deck_id: str) -> PlainTextResponse:
        path = artifacts(deck_id).caption_file
        if not path.is_file():
            raise HTTPException(404, "not rendered yet")
        return PlainTextResponse(path.read_text(encoding="utf-8"))

    @router.get("/{deck_id}/download")
    def download(deck_id: str) -> StreamingResponse:
        """Everything a human needs to upload the carousel by hand, as one zip."""
        found = artifacts(deck_id)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in found.files():
                archive.write(path, arcname=str(Path(deck_id) / path.relative_to(found.directory)))
        buffer.seek(0)
        return StreamingResponse(
            buffer, media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{deck_id}.zip"'},
        )

    # -- re-render ---------------------------------------------------------

    @router.post("/{deck_id}/render")
    def rerender(deck_id: str) -> dict:
        """Re-render an existing deck after a hand edit to its deck.json."""
        artifacts(deck_id)
        job = container.jobs.create(topic=deck_id, deck_id=deck_id)
        container.job_runner.submit(
            job, lambda observer: container.pipeline.rerender(deck_id, observer))
        return {"job_id": job.id, "status": job.status}

    return router


def _reject_bad_request(request: DeckRequest, container: ApplicationContainer) -> None:
    if request.archetype not in Archetype.values():
        raise HTTPException(400, f"archetype must be one of {Archetype.values()}")
    if request.palette not in Palette.values():
        raise HTTPException(400, "palette must be 'dark' or 'light'")
    if request.framework not in container.frameworks:
        raise HTTPException(400, f"framework must be one of {container.frameworks.choices()}")
    if not request.has_source and len((request.topic or "").strip()) < MIN_TOPIC_CHARS:
        raise HTTPException(400, "give a topic, or a source_url / source_text to draw one from")
