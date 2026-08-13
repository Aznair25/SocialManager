"""HTTP delivery. Thin by design — routers translate requests into service calls."""
from .app import create_app

__all__ = ["create_app"]
