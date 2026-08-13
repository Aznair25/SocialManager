"""Implementations of the ports: OpenAI, Playwright, the filesystem.

This is the only layer that imports third-party SDKs. Those imports are made
lazily inside methods so that importing the package — for the CLI's `validate`
command, or for the test suite — does not require openai or playwright to be
installed.
"""
