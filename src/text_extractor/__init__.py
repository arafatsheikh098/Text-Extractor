"""Self-hosted PDF and image to text extractor.

The public entry points are :func:`text_extractor.app.create_app` (for WSGI
servers and tests) and :func:`text_extractor.cli.main` (for the command line).
"""

from __future__ import annotations

__all__ = ["__version__", "create_app"]

__version__ = "1.0.0"


def create_app(*args, **kwargs):  # pragma: no cover - re-export shim
    from .app import create_app as _create_app

    return _create_app(*args, **kwargs)
