"""Job polling — the browser asks this every second while a deck builds."""
from fastapi import APIRouter, HTTPException

from ...container import ApplicationContainer


def build_job_router(container: ApplicationContainer) -> APIRouter:
    router = APIRouter(prefix="/api/jobs", tags=["jobs"])

    @router.get("/{job_id}")
    def get_job(job_id: str) -> dict:
        snapshot = container.jobs.snapshot(job_id)
        if snapshot is None:
            raise HTTPException(404, "unknown job")
        return snapshot

    return router
