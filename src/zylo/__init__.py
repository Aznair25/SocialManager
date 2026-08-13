"""Zylo Deck Studio — topic or source URL to a rendered Instagram carousel.

Layering (dependencies point inwards only):

    domain/     Deck model, validation rules, prompt text. Pure Python, no I/O.
    ports.py    Protocols the outer layers implement — the seams for testing.
    adapters/   OpenAI, Playwright and filesystem implementations of those ports.
    rendering/  deck -> HTML. Pure; the screenshotting is a port.
    services/   Use cases: generate, render, run the pipeline, track jobs.
    api/, cli/  Delivery. Thin — they translate requests into service calls.
    container.py  The composition root, where concrete adapters are chosen.

Nothing in domain/ or services/ imports openai, playwright or fastapi, which is
what lets the whole pipeline run against fakes in the test suite.
"""

__version__ = "2.0"
