#!/usr/bin/env python3
"""Compatibility shim — the implementation lives in src/zylo/.

    python src/validate.py decks/<dir>/deck.json

Equivalent to `python -m zylo validate`. The rules themselves are in
src/zylo/domain/validation/rules.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from zylo.cli.commands import ValidateCommand  # noqa: E402
from zylo.cli.main import run_command  # noqa: E402

if __name__ == "__main__":
    sys.exit(run_command(ValidateCommand(), prog="python src/validate.py",
                         usage="python src/validate.py decks/<dir>/deck.json"))
