#!/usr/bin/env python3
"""Compatibility shim — the implementation lives in src/zylo/.

    python src/generate.py "How AI agents cut support costs" --archetype insight
    python src/generate.py "AI ROI numbers" --archetype stat --palette dark --render

Equivalent to `python -m zylo generate`. See src/zylo/services/generation.py for
the generation loop and src/zylo/prompts/ for the prompt text.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from zylo.cli.commands import GenerateCommand  # noqa: E402
from zylo.cli.main import run_command  # noqa: E402

if __name__ == "__main__":
    sys.exit(run_command(GenerateCommand(), prog="python src/generate.py"))
