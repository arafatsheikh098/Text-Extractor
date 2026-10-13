"""Unit tests for :class:`text_extractor.config.Settings`."""

from __future__ import annotations

import os
from unittest.mock import patch

from text_extractor.config import Settings


def test_settings_default_values() -> None:
    s = Settings()
    assert s.host == "127.0.0.1"
    assert s.port == 8765
    assert s.restrict_host is True
    assert s.max_upload_mb == 200
    assert s.max_upload_bytes == 200 * 1024 * 1024
    assert s.is_local_host("localhost")
    assert s.is_local_host("127.0.0.1:8765")
    assert not s.is_local_host("evil.com")


def test_settings_from_env_overrides() -> None:
    env = {
        "HOST": "0.0.0.0",
        "PORT": "9000",
        "ALLOW_REMOTE": "1",
        "MAX_UPLOAD_MB": "50",
        "MAX_FILES": "10",
        "OCR_WORKERS": "2",
        "TRUSTED_PROXIES": "1",
    }
    with patch.dict(os.environ, env, clear=True):
        s = Settings.from_env()
    assert s.host == "0.0.0.0"
    assert s.port == 9000
    assert s.restrict_host is False
    assert s.max_upload_mb == 50
    assert s.max_files == 10
    assert s.ocr_workers == 2
    assert s.trusted_proxies == 1


def test_settings_from_env_invalid_int_falls_back() -> None:
    env = {
        "PORT": "invalid-port",
        "MAX_UPLOAD_MB": "not-a-number",
    }
    with patch.dict(os.environ, env, clear=True):
        s = Settings.from_env()
    assert s.port == 8765
    assert s.max_upload_mb == 200
