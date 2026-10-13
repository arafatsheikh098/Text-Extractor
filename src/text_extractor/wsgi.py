"""WSGI entry point. Use this for ``gunicorn text_extractor.wsgi:app``."""

from __future__ import annotations

from .app import create_app
from .config import Settings

app = create_app(Settings.from_env(open_browser=False))
