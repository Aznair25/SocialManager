"""Background jobs for the web UI.

A deck build takes minutes, so the API starts one and hands back a job id to
poll. Chromium and the deck directory are shared state, so a single lock keeps
it to one build at a time — simple, and safe.
"""
import threading
import uuid
from dataclasses import dataclass, field
from typing import Callable

from ..domain.errors import ZyloError
from .pipeline import Stage


class Status:
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class Job:
    id: str
    status: str = Status.QUEUED
    stage: str = Stage.QUEUED
    log: list[str] = field(default_factory=list)
    deck_id: str | None = None
    error: str | None = None
    topic: str | None = None

    def snapshot(self) -> dict:
        """A copy safe to serialise while the worker thread is still writing."""
        return {"id": self.id, "status": self.status, "stage": self.stage,
                "log": list(self.log), "deck_id": self.deck_id,
                "error": self.error, "topic": self.topic}


class JobStore:
    """In-memory, thread-safe. Jobs live for the lifetime of the process."""

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.RLock()

    def create(self, topic: str | None = None, deck_id: str | None = None) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], topic=topic, deck_id=deck_id)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def snapshot(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.snapshot() if job else None

    def update(self, job_id: str, **fields) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for key, value in fields.items():
                setattr(job, key, value)

    def append_log(self, job_id: str, line: str) -> None:
        line = str(line).strip()
        if not line:
            return
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.log.append(line)


class JobObserver:
    """Implements `PipelineObserver` by writing into a job record."""

    def __init__(self, store: JobStore, job_id: str):
        self._store = store
        self._job_id = job_id

    def stage(self, name: str, deck_id: str | None = None) -> None:
        fields = {"stage": name, "status": self._status_for(name)}
        if deck_id:
            fields["deck_id"] = deck_id
        self._store.update(self._job_id, **fields)

    def emit(self, message: str) -> None:
        self._store.append_log(self._job_id, message)

    def failed(self, message: str) -> None:
        self._store.update(self._job_id, status=Status.ERROR, stage=Stage.FAILED, error=message)
        self.emit(f"FAILED: {message}")

    @staticmethod
    def _status_for(stage: str) -> str:
        if stage == Stage.DONE:
            return Status.DONE
        if stage == Stage.FAILED:
            return Status.ERROR
        return Status.RUNNING


class JobRunner:
    """Runs work on a daemon thread, serialised behind one lock.

    Playwright's sync API refuses to start inside an asyncio event loop, which is
    the other reason this never runs on the FastAPI request thread.
    """

    # `threading.Lock` is a factory, not a class, so the annotation is quoted —
    # unquoted it is evaluated at import time and raises.
    def __init__(self, store: JobStore, lock: "threading.Lock | None" = None):
        self._store = store
        self._lock = lock or threading.Lock()

    @property
    def store(self) -> JobStore:
        return self._store

    def submit(self, job: Job, work: Callable[[JobObserver], None]) -> Job:
        observer = JobObserver(self._store, job.id)
        threading.Thread(target=self._run, args=(observer, work), daemon=True).start()
        return job

    def _run(self, observer: JobObserver, work: Callable[[JobObserver], None]) -> None:
        try:
            with self._lock:
                work(observer)
        except ZyloError as exc:
            observer.failed(str(exc))
        except Exception as exc:  # unexpected — still surface it to the UI
            observer.failed(f"{type(exc).__name__}: {exc}")
