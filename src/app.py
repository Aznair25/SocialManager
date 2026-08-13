#!/usr/bin/env python3
"""HTTP API + web UI — compatibility shim; the implementation lives in src/zylo/.

    python src/app.py            (then open http://127.0.0.1:8777, or --port)

Equivalent to `python -m zylo serve`. `app` is exported for ASGI servers:

    uvicorn app:app --app-dir src

Setup: pip install -r requirements.txt && playwright install chromium
       cp .env.example .env  (add OPENAI_API_KEY)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from zylo.api import create_app  # noqa: E402
from zylo.cli.commands import ServeCommand  # noqa: E402
from zylo.cli.main import run_command  # noqa: E402
from zylo.container import ApplicationContainer  # noqa: E402

#: Module-level ASGI app, for `uvicorn app:app`.
app = create_app(ApplicationContainer.default())

if __name__ == "__main__":
    sys.exit(run_command(ServeCommand(), prog="python src/app.py"))
