#!/usr/bin/env python3
"""Compatibility shim — the implementation lives in src/zylo/.

    python src/render.py decks/<dir>/deck.json

Equivalent to `python -m zylo render`. Slide HTML is built in
src/zylo/rendering/ and screenshotted through the Playwright adapter.

Setup (once): pip install -r requirements.txt && playwright install chromium
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from zylo.cli.commands import RenderCommand  # noqa: E402
from zylo.cli.main import run_command  # noqa: E402

if __name__ == "__main__":
    sys.exit(run_command(RenderCommand(), prog="python src/render.py",
                         usage="python src/render.py decks/<dir>/deck.json"))
