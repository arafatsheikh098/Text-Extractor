"""Unit tests for :mod:`text_extractor.processing`."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from PIL import Image

from text_extractor.config import Settings
from text_extractor.errors import Cancelled
from text_extractor.jobs import FileState
from text_extractor.processing import join_pages, process_image


@dataclass
class _FakeCtx:
    options: dict[str, Any]
    cancel: threading.Event = field(default_factory=threading.Event)


def test_join_pages_with_markers() -> None:
    out = join_pages([(1, "hello"), (2, "world")], markers=True)
    assert out == "--- Page 1 ---\nhello\n\n--- Page 2 ---\nworld"


def test_join_pages_without_markers() -> None:
    assert join_pages([(1, "a"), (2, "b")], markers=False) == "a\n\nb"


def test_join_pages_strips_outer_whitespace() -> None:
    assert join_pages([(1, "  hi  ")], markers=False) == "hi"


def test_process_image_runs_ocr(tmp_path: Path, settings: Settings) -> None:
    path = tmp_path / "x.png"
    Image.new("RGB", (16, 16), color="white").save(path, format="PNG")
    fs = FileState(id="f0", name="x.png", path=str(path), ext=".png")
    ctx = _FakeCtx(options={"lang": "eng", "dpi": 300, "force_ocr": False, "page_markers": False})

    with patch("text_extractor.processing.ocr_image", return_value="hello world") as m:
        process_image(fs, ctx, settings)

    m.assert_called_once()
    assert fs.text == "hello world"
    assert fs.ocr_pages == 1
    assert fs.pages_total == 1


def test_process_image_respects_cancel(tmp_path: Path, settings: Settings) -> None:
    path = tmp_path / "x.png"
    Image.new("RGB", (16, 16), color="white").save(path, format="PNG")
    fs = FileState(id="f0", name="x.png", path=str(path), ext=".png")
    ctx = _FakeCtx(
        options={"lang": "eng", "dpi": 300, "force_ocr": False, "page_markers": False}
    )
    ctx.cancel.set()

    with pytest.raises(Cancelled):
        process_image(fs, ctx, settings)


def test_process_pdf_digital_text(tmp_path: Path, settings: Settings) -> None:
    import pymupdf

    path = tmp_path / "doc.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), "This is a digital test PDF with more than twenty characters.")
    doc.save(str(path))
    doc.close()

    from text_extractor.processing import process_pdf

    fs = FileState(id="f0", name="doc.pdf", path=str(path), ext=".pdf")
    ctx = _FakeCtx(options={"lang": "eng", "dpi": 300, "force_ocr": False, "page_markers": True})
    process_pdf(fs, ctx, settings)

    assert "This is a digital test PDF" in fs.text
    assert fs.text_pages == 1
    assert fs.ocr_pages == 0
    assert fs.pages_total == 1


def test_process_pdf_fallback_to_ocr(tmp_path: Path, settings: Settings) -> None:
    import pymupdf

    path = tmp_path / "scan.pdf"
    doc = pymupdf.open()
    doc.new_page()  # blank page
    doc.save(str(path))
    doc.close()

    from text_extractor.processing import process_pdf

    fs = FileState(id="f0", name="scan.pdf", path=str(path), ext=".pdf")
    ctx = _FakeCtx(options={"lang": "eng", "dpi": 300, "force_ocr": False, "page_markers": False})

    with patch("text_extractor.processing.ocr_image", return_value="scanned content text") as m_ocr:
        process_pdf(fs, ctx, settings)

    m_ocr.assert_called_once()
    assert fs.text == "scanned content text"
    assert fs.ocr_pages == 1
    assert fs.text_pages == 0

