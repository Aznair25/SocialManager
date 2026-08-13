"""Terminal delivery. Same services the HTTP API uses, different front door."""
from .main import main, run_command

__all__ = ["main", "run_command"]
