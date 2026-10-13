"""OCR-related helpers: configuration strings, capability probing, and the
``describe_error`` mapper that turns low-level failures into messages a human
will understand.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image, ImageOps

from .config import Settings
from .errors import UserFacingError


def tess_config(settings: Settings, *, psm: int | None = None) -> str:
    """Build the ``--psm`` and ``--tessdata-dir`` portion of the tesseract CLI string."""
    parts: list[str] = []
    if psm is not None:
        parts.append(f"--psm {psm}")
    if settings.tessdata is not None:
        parts.append(f'--tessdata-dir "{Path(settings.tessdata).as_posix()}"')
    return " ".join(parts)


def tesseract_info(settings: Settings) -> tuple[bool, str | None, list[str]]:
    """Return ``(installed, version, language_codes)``."""
    try:
        version = str(pytesseract.get_tesseract_version())
        langs = [c for c in pytesseract.get_languages(config=tess_config(settings)) if c != "osd"]
        return True, version, sorted(langs)
    except pytesseract.TesseractNotFoundError:
        return False, None, []
    except Exception:
        return False, None, []


def ocr_image(img: Image.Image, lang: str, settings: Settings) -> str:
    """OCR a single PIL image, raising :class:`UserFacingError` for real failures."""
    img = ImageOps.exif_transpose(img)
    img = ImageOps.autocontrast(img.convert("L"))
    try:
        return pytesseract.image_to_string(
            img,
            lang=lang,
            config=tess_config(settings, psm=3),
            timeout=settings.ocr_timeout_seconds,
        ).strip()
    except pytesseract.TesseractNotFoundError as exc:
        raise UserFacingError(
            "Tesseract is not installed, so scanned pages cannot be read. "
            "See the setup steps in the README."
        ) from exc


def describe_error(exc: BaseException, settings: Settings | None = None) -> str:
    """Turn a low-level exception into a single human-friendly sentence."""
    del settings  # kept for API symmetry / future per-setting tweaks
    if isinstance(exc, UserFacingError):
        return str(exc)
    msg = str(exc)
    if isinstance(exc, Image.DecompressionBombError) or "decompression bomb" in msg.lower():
        return "This image is too large to process. Make it smaller and try again."
    if isinstance(exc, Image.UnidentifiedImageError):
        return "This image could not be read. It may be damaged or not a real image."
    if isinstance(exc, RuntimeError) and "timeout" in msg.lower():
        return "Reading took too long. Try a lower scan quality or a smaller file."
    pymupdf_data_error = getattr(pymupdf, "FileDataError", ())
    if isinstance(exc, pymupdf_data_error) or "Failed to open file" in msg:
        return "This file could not be read. It may be damaged or not a real PDF."
    if isinstance(exc, pytesseract.TesseractError):
        return "The text reader failed on this file. Try a different language or scan quality."
    return "Something went wrong while reading this file."


__all__ = ["describe_error", "ocr_image", "tess_config", "tesseract_info"]
