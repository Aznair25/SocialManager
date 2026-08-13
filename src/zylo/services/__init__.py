"""Use cases: generate a deck, render one, run the whole pipeline, track jobs.

Everything here is constructor-injected with ports, so the entire pipeline runs
in tests against fakes — no API key, no browser, no network.
"""
