"""Unit tests for :mod:`text_extractor.ocr`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytesseract
import pytest
from PIL import Image

from text_extractor.config import Settings
from text_extractor.errors import UserFacingError
from text_extractor.ocr import describe_error, ocr_image, tess_config, tesseract_info


def test_tess_config_no_tessdata() -> None:
    s = Settings()
    assert tess_config(s) == ""
    assert tess_config(s, psm=3) == "--psm 3"


def test_tess_config_with_tessdata(tmp_path: Path) -> None:
    s = Settings(tessdata=tmp_path)
    out = tess_config(s)
    assert out.startswith("--tessdata-dir ")
    assert tmp_path.as_posix() in out


def test_describe_error_user_facing_passthrough() -> None:
    err = UserFacingError("nope")
    assert describe_error(err) == "nope"


def test_describe_error_decompression_bomb() -> None:
    err = Image.DecompressionBombError("kaboom")
    assert "too large" in describe_error(err).lower()


def test_describe_error_unidentified_image() -> None:
    err = Image.UnidentifiedImageError()
    assert "could not be read" in describe_error(err).lower()


def test_describe_error_timeout() -> None:
    err = RuntimeError("Pytesseract process timeout")
    assert "too long" in describe_error(err).lower()


def test_describe_error_tesseract() -> None:
    err = pytesseract.TesseractError("oops", "stderr")
    assert "text reader failed" in describe_error(err).lower()


def test_describe_error_unknown() -> None:
    assert describe_error(ValueError("???")) == "Something went wrong while reading this file."


def test_tesseract_info_handles_missing_binary() -> None:
    with patch("text_extractor.ocr.pytesseract.get_tesseract_version", side_effect=pytesseract.TesseractNotFoundError):
        installed, version, codes = tesseract_info(Settings())
    assert installed is False
    assert version is None
    assert codes == []


def test_ocr_image_raises_user_facing_when_tesseract_missing() -> None:
    with patch("text_extractor.ocr.pytesseract.image_to_string", side_effect=pytesseract.TesseractNotFoundError):
        img = Image.new("RGB", (8, 8), color="white")
        with pytest.raises(UserFacingError) as ei:
            ocr_image(img, "eng", Settings())
    assert "Tesseract is not installed" in str(ei.value)
