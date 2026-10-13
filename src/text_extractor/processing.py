"""File-to-text processing: PDFs and images.

The two ``process_*`` functions take a :class:`FileState` (a thin mutable
record of one uploaded file) and a :class:`ProcessContext` that exposes the
job-wide options and a cancellation event. The functions update ``fs`` in
place so the caller can stream progress back to the browser.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Mapping
from typing import Protocol

import pymupdf
from PIL import Image, ImageSequence

from .config import Settings
from .errors import Cancelled, UserFacingError
from .ocr import describe_error, ocr_image


class FileStateLike(Protocol):
    """Minimal contract a :class:`processing` consumer must satisfy."""

    path: str
    ext: str
    pages_total: int
    pages_done: int
    text_pages: int
    ocr_pages: int
    text: str


class ProcessContext(Protocol):
    """The bits of a job the processors care about."""

    options: Mapping[str, object]
    cancel: threading.Event


def join_pages(parts: list[tuple[int, str]], markers: bool) -> str:
    """Glue ``(page_number, text)`` pairs into the final body."""
    if markers:
        body = "\n\n".join(f"--- Page {n} ---\n{t}" for n, t in parts)
    else:
        body = "\n\n".join(t for _, t in parts)
    return body.strip()


def process_pdf(fs: FileStateLike, ctx: ProcessContext, settings: Settings) -> None:
    """Extract text from a PDF, falling back to OCR for scanned pages."""
    parts: list[tuple[int, str]] = []
    text_pages = ocr_pages = 0
    with pymupdf.open(fs.path) as doc:
        if doc.needs_pass:
            raise UserFacingError("This PDF is password protected. Remove the password and try again.")
        fs.pages_total = doc.page_count
        if doc.page_count == 0:
            raise UserFacingError("This PDF has no pages.")
        for number, page in enumerate(doc, start=1):
            if ctx.cancel.is_set():
                raise Cancelled()
            text = "" if ctx.options["force_ocr"] else page.get_text("text").strip()
            if len(text) < settings.min_text_chars:
                dpi = int(ctx.options["dpi"])  # type: ignore[arg-type]
                width_in = page.rect.width / 72
                height_in = page.rect.height / 72
                if width_in * height_in * dpi * dpi > settings.max_render_pixels:
                    dpi = max(72, int(math.sqrt(settings.max_render_pixels / (width_in * height_in))))
                try:
                    pix = page.get_pixmap(dpi=dpi)
                    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    text = ocr_image(img, str(ctx.options["lang"]), settings)
                except UserFacingError:
                    raise
                except Exception as exc:
                    raise UserFacingError(f"Page {number}: {describe_error(exc, settings)}") from exc
                ocr_pages += 1
            else:
                text_pages += 1
            parts.append((number, text))
            fs.pages_done = number
    fs.text_pages = text_pages
    fs.ocr_pages = ocr_pages
    fs.text = join_pages(parts, bool(ctx.options["page_markers"]))


def process_image(fs: FileStateLike, ctx: ProcessContext, settings: Settings) -> None:
    """OCR an image, walking every frame of a multi-page TIFF."""
    parts: list[tuple[int, str]] = []
    with Image.open(fs.path) as img:
        is_tiff = fs.ext in {".tif", ".tiff"}
        if is_tiff:
            total = min(getattr(img, "n_frames", 1), settings.max_tiff_frames)
            frames = ImageSequence.Iterator(img)
        else:
            total = 1
            frames = [img]
        fs.pages_total = total
        for number, frame in enumerate(frames, start=1):
            if number > settings.max_tiff_frames:
                break
            if ctx.cancel.is_set():
                raise Cancelled()
            parts.append((number, ocr_image(frame, str(ctx.options["lang"]), settings)))
            fs.pages_done = number
    fs.ocr_pages = len(parts)
    fs.text = join_pages(parts, bool(ctx.options["page_markers"]) and len(parts) > 1)


__all__ = ["FileStateLike", "ProcessContext", "join_pages", "process_image", "process_pdf"]
