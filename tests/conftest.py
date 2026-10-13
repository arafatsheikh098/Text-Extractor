"""Shared pytest fixtures: an app, a test client, and a tiny PNG/PDF on disk."""

from __future__ import annotations

import io
from concurrent.futures import Executor
from pathlib import Path

import pytest
from PIL import Image

from text_extractor.app import create_app
from text_extractor.config import Settings
from text_extractor.jobs import JobStore


class _InlineExecutor(Executor):
    """A trivial executor that runs jobs on the calling thread.

    This makes the test suite deterministic — no race conditions between the
    test thread and a background worker.
    """

    def submit(self, fn, /, *args, **kwargs):  # type: ignore[override]
        class _Future:
            def __init__(self) -> None:
                self._result = None
                self._exc = None
                try:
                    self._result = fn(*args, **kwargs)
                except BaseException as exc:
                    self._exc = exc

            def result(self):
                if self._exc is not None:
                    raise self._exc
                return self._result

            def exception(self):
                return self._exc

        return _Future()

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:  # type: ignore[override]
        return None


@pytest.fixture
def settings() -> Settings:
    return Settings(max_upload_mb=10, max_files=5)


@pytest.fixture
def inline_executor() -> _InlineExecutor:
    return _InlineExecutor()


@pytest.fixture
def job_store(settings: Settings) -> JobStore:
    return JobStore(settings)


@pytest.fixture
def app(settings: Settings, inline_executor: _InlineExecutor, job_store: JobStore):
    app = create_app(settings, executor=inline_executor, job_store=job_store)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def tiny_png(tmp_path: Path) -> Path:
    """A small but valid PNG that PIL can open."""
    path = tmp_path / "tiny.png"
    img = Image.new("RGB", (32, 32), color=(255, 255, 255))
    # Draw a single dark pixel so any sane OCR call gets at least one glyph.
    img.putpixel((4, 4), (0, 0, 0))
    img.save(path, format="PNG")
    return path


@pytest.fixture
def tiny_png_bytes(tiny_png: Path) -> bytes:
    return tiny_png.read_bytes()


@pytest.fixture
def in_memory_png() -> bytes:
    """PNG bytes without touching the filesystem."""
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color="white").save(buf, format="PNG")
    return buf.getvalue()
