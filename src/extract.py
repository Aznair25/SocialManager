#!/usr/bin/env python3
"""Compatibility shim — the implementation lives in src/zylo/.

    python src/extract.py <url>

Equivalent to `python -m zylo extract`. Cleaning and wall-detection are in
src/zylo/adapters/extraction.py; the browser fetch is in adapters/browser.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from zylo.cli.commands import ExtractCommand  # noqa: E402
from zylo.cli.main import run_command  # noqa: E402

if __name__ == "__main__":
    sys.exit(run_command(ExtractCommand(), prog="python src/extract.py",
                         usage="python src/extract.py <url>"))
