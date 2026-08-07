#!/usr/bin/env python3
"""app.py — HTTP API + web UI wrapping the deck pipeline.

End to end: topic -> generate.py (OpenAI) -> validate.py -> render.py -> PNGs.
Non-technical users get the browser UI at /; everything it does is also a
plain REST call, so the same endpoints work from curl or another service.

Run: python src/app.py           (then open http://127.0.0.1:8777, or --port)
Setup: pip install -r requirements.txt && playwright install chromium
       cp .env.example .env  (add OPENAI_API_KEY)
"""
import io
import json
import threading
import uuid
import zipfile
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract import ExtractError, extract_from_url  # noqa: E402
from generate import ARCHETYPE_GUIDE, GenerationError, generate, load_env  # noqa: E402
from render import RenderError, render_deck  # noqa: E402
from validate import validate_deck  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DECKS = ROOT / "decks"
WEB = ROOT / "web"


load_env()
app = FastAPI(title="Zylo Deck Studio", version="1.0")

# job_id -> {status, stage, log[], deck_id, error}
JOBS = {}
JOBS_LOCK = threading.Lock()
# Chromium + the deck dir are shared state; one deck at a time keeps it simple and safe.
PIPELINE_LOCK = threading.Lock()


class DeckRequest(BaseModel):
    topic: str | None = Field(default=None, max_length=300)
    archetype: str = "insight"
    palette: str = "dark"
    notes: str | None = Field(default=None, max_length=1000)
    slug: str | None = None
    pillar: str | None = None
    # Optional reference material: a URL to read, or text pasted in when a site blocks the fetch.
    source_url: str | None = Field(default=None, max_length=2000)
    source_text: str | None = Field(default=None, max_length=40000)


def _set(job_id, **kw):
    with JOBS_LOCK:
        JOBS[job_id].update(kw)


def _log(job_id, line):
    line = str(line).strip()
    if not line:
        return
    with JOBS_LOCK:
        JOBS[job_id]["log"].append(line)


def _deck_dir(deck_id):
    """Resolve a deck id to its directory, refusing anything outside decks/."""
    d = (DECKS / deck_id).resolve()
    if d.parent != DECKS.resolve() or not d.is_dir():
        raise HTTPException(404, f"deck '{deck_id}' not found")
    return d


def run_pipeline(job_id, req: DeckRequest):
    """Generate -> validate -> render. Runs on a worker thread: Playwright's sync
    API refuses to start inside an asyncio event loop."""
    try:
        with PIPELINE_LOCK:
            source = None
            if req.source_url:
                _set(job_id, status="running", stage="reading")
                _log(job_id, f"Reading {req.source_url}")
                source = extract_from_url(req.source_url, on_event=lambda m: _log(job_id, m))
            elif req.source_text:
                _set(job_id, status="running", stage="reading")
                source = {"url": "", "title": "", "text": req.source_text.strip()}
                _log(job_id, f"Using {len(source['text'])} characters of pasted source text")

            _set(job_id, status="running", stage="generating")
            _log(job_id, "Writing the deck" + (" from the source points" if source else f" for: {req.topic}"))
            deck = generate(
                req.topic, req.archetype, req.palette,
                slug=req.slug, pillar=req.pillar, notes=req.notes,
                on_event=lambda m: _log(job_id, m), source=source,
            )

            _set(job_id, stage="validating", deck_id=deck["id"])
            errors, warnings = validate_deck(deck)
            for w in warnings:
                _log(job_id, f"WARN {w}")
            if errors:
                raise GenerationError("; ".join(errors))
            _log(job_id, "Validation passed")

            out_dir = DECKS / deck["id"]
            out_dir.mkdir(parents=True, exist_ok=True)
            deck_file = out_dir / "deck.json"
            deck_file.write_text(json.dumps(deck, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            _log(job_id, f"Wrote {deck_file.relative_to(ROOT)}")

            _set(job_id, stage="rendering")
            render_deck(deck_file, on_event=lambda m: _log(job_id, m))

            _set(job_id, status="done", stage="done")
            _log(job_id, "Deck ready for review")
    except (ExtractError, GenerationError, RenderError) as e:
        _set(job_id, status="error", stage="failed", error=str(e))
        _log(job_id, f"FAILED: {e}")
    except Exception as e:  # unexpected — still surface it to the UI
        _set(job_id, status="error", stage="failed", error=f"{type(e).__name__}: {e}")
        _log(job_id, f"FAILED: {type(e).__name__}: {e}")


@app.post("/api/decks")
def create_deck(req: DeckRequest):
    """Kick off an end-to-end deck build. Returns immediately with a job id."""
    if req.archetype not in ARCHETYPE_GUIDE:
        raise HTTPException(400, f"archetype must be one of {sorted(ARCHETYPE_GUIDE)}")
    if req.palette not in ("dark", "light"):
        raise HTTPException(400, "palette must be 'dark' or 'light'")
    has_source = bool((req.source_url or "").strip() or (req.source_text or "").strip())
    if not has_source and len((req.topic or "").strip()) < 3:
        raise HTTPException(400, "give a topic, or a source_url / source_text to draw one from")

    job_id = uuid.uuid4().hex[:12]
    with JOBS_LOCK:
        JOBS[job_id] = {"id": job_id, "status": "queued", "stage": "queued",
                        "log": [], "deck_id": None, "error": None, "topic": req.topic}
    threading.Thread(target=run_pipeline, args=(job_id, req), daemon=True).start()
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "unknown job")
        return dict(job, log=list(job["log"]))


@app.get("/api/decks")
def list_decks():
    out = []
    if DECKS.is_dir():
        for d in sorted(DECKS.iterdir(), reverse=True):
            f = d / "deck.json"
            if not f.is_file():
                continue
            try:
                deck = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            out.append({
                "id": deck.get("id", d.name),
                "topic": deck.get("topic", ""),
                "archetype": deck.get("archetype"),
                "palette": deck.get("palette"),
                "slides": len(deck.get("slides", [])),
                "rendered": (d / "contact-sheet.png").is_file(),
            })
    return {"decks": out}


@app.get("/api/decks/{deck_id}")
def get_deck(deck_id: str):
    d = _deck_dir(deck_id)
    deck = json.loads((d / "deck.json").read_text(encoding="utf-8"))
    slides = sorted(p.name for p in (d / "slides").glob("*.png")) if (d / "slides").is_dir() else []
    caption = (d / "caption.txt").read_text(encoding="utf-8") if (d / "caption.txt").is_file() else ""
    return {"deck": deck, "slides": slides, "caption": caption,
            "contact_sheet": (d / "contact-sheet.png").is_file()}


@app.post("/api/decks/{deck_id}/render")
def rerender(deck_id: str):
    """Re-render an existing deck after a hand edit to its deck.json."""
    d = _deck_dir(deck_id)
    job_id = uuid.uuid4().hex[:12]
    with JOBS_LOCK:
        JOBS[job_id] = {"id": job_id, "status": "queued", "stage": "queued",
                        "log": [], "deck_id": deck_id, "error": None, "topic": deck_id}

    def work():
        try:
            with PIPELINE_LOCK:
                _set(job_id, status="running", stage="rendering")
                render_deck(d / "deck.json", on_event=lambda m: _log(job_id, m))
                _set(job_id, status="done", stage="done")
        except RenderError as e:
            _set(job_id, status="error", stage="failed", error=str(e))
            _log(job_id, f"FAILED: {e}")

    threading.Thread(target=work, daemon=True).start()
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/decks/{deck_id}/slides/{name}")
def get_slide(deck_id: str, name: str):
    d = _deck_dir(deck_id)
    p = (d / "slides" / name).resolve()
    if p.parent != (d / "slides").resolve() or not p.is_file():
        raise HTTPException(404, "slide not found")
    return FileResponse(p, media_type="image/png")


@app.get("/api/decks/{deck_id}/contact-sheet.png")
def get_sheet(deck_id: str):
    p = _deck_dir(deck_id) / "contact-sheet.png"
    if not p.is_file():
        raise HTTPException(404, "not rendered yet")
    return FileResponse(p, media_type="image/png")


@app.get("/api/decks/{deck_id}/caption.txt")
def get_caption(deck_id: str):
    p = _deck_dir(deck_id) / "caption.txt"
    if not p.is_file():
        raise HTTPException(404, "not rendered yet")
    return PlainTextResponse(p.read_text(encoding="utf-8"))


@app.get("/api/decks/{deck_id}/download")
def download(deck_id: str):
    """Everything a human needs to upload the carousel by hand, as one zip."""
    d = _deck_dir(deck_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(d.rglob("*")):
            if p.is_file():
                z.write(p, arcname=str(Path(deck_id) / p.relative_to(d)))
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{deck_id}.zip"'},
    )


@app.get("/api/config")
def config():
    import os
    return {"archetypes": sorted(ARCHETYPE_GUIDE),
            "palettes": ["dark", "light"],
            "model": os.environ.get("ZYLO_MODEL", "gpt-5.1"),
            "api_key_set": bool(os.environ.get("OPENAI_API_KEY"))}


@app.get("/", response_class=HTMLResponse)
def index():
    return (WEB / "index.html").read_text(encoding="utf-8")


if __name__ == "__main__":
    import argparse
    import os
    import socket

    import uvicorn

    ap = argparse.ArgumentParser(description="Run the Zylo Deck Studio web app")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=int(os.environ.get("ZYLO_PORT", 8777)))
    a = ap.parse_args()

    # Bind-check first: a busy port otherwise fails deep in uvicorn's output where
    # a non-technical operator will not see it.
    probe = socket.socket()
    try:
        probe.bind((a.host, a.port))
    except OSError:
        sys.exit(f"Port {a.port} is already in use. Run with --port <other> (e.g. --port 8778).")
    finally:
        probe.close()

    print(f"\n  Zylo Deck Studio  ->  http://{a.host}:{a.port}\n  (Ctrl+C to stop)\n")
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")
