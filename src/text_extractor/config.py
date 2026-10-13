"""Runtime configuration for the text extractor service.

The defaults are conservative: local-only listening, a single OCR worker (OCR
is CPU heavy), and a generous upload limit. Override via :class:`Settings` when
building the Flask app in tests, or via command line flags / environment
variables in :mod:`text_extractor.cli`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

# Module-level constants. They are not dataclass fields because the dataclass
# machinery in Python 3.14 refuses to combine ClassVar with default_factory.
IMAGE_EXTS: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif"})
ALLOWED_EXTS: frozenset[str] = IMAGE_EXTS | {".pdf"}
DPI_CHOICES: frozenset[int] = frozenset({150, 200, 300, 400})
DEFAULT_DPI: int = 300
LOCAL_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost", "[::1]", "::1"})
LANG_NAMES: dict[str, str] = {
    "eng": "English",
    "ben": "Bangla",
    "hin": "Hindi",
    "urd": "Urdu",
    "ara": "Arabic",
    "asm": "Assamese",
    "nep": "Nepali",
    "fra": "French",
    "deu": "German",
    "spa": "Spanish",
}


@dataclass(frozen=True)
class Settings:
    """Immutable, hashable configuration for one app instance."""

    host: str = "127.0.0.1"
    port: int = 8765
    tessdata: Path | None = None
    restrict_host: bool = True
    max_upload_mb: int = 200
    max_files: int = 30
    ocr_workers: int = 1
    job_ttl_seconds: int = 2 * 60 * 60
    max_jobs_kept: int = 20
    ocr_timeout_seconds: int = 180
    max_tiff_frames: int = 500
    min_text_chars: int = 20
    max_render_pixels: int = 120_000_000
    open_browser: bool = True
    trusted_proxies: int = 0

    # Convenience aliases so callers can still write ``settings.allowed_exts``.
    image_exts: ClassVar[frozenset[str]] = IMAGE_EXTS
    allowed_exts: ClassVar[frozenset[str]] = ALLOWED_EXTS
    dpi_choices: ClassVar[frozenset[int]] = DPI_CHOICES
    default_dpi: ClassVar[int] = DEFAULT_DPI
    local_hosts: ClassVar[frozenset[str]] = LOCAL_HOSTS
    lang_names: ClassVar[dict[str, str]] = LANG_NAMES

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def is_local_host(self, host: str) -> bool:
        if not host:
            return False
        # Strip an optional :port suffix. Hostnames can themselves contain
        # colons (IPv6) so we only strip the trailing one.
        bare = host.rsplit(":", 1)[0] if not host.startswith("[") else host
        bare = bare.strip("[]")
        return bare.lower() in {h.lower().strip("[]") for h in self.local_hosts}

    @classmethod
    def from_env(cls, **overrides: Any) -> Settings:
        """Construct Settings from environment variables with optional parameter overrides."""

        def _env_truthy(val: str | None) -> bool:
            return str(val or "").strip().lower() in {"1", "true", "yes", "on"}

        def _env_int(name: str, default: int) -> int:
            raw = os.environ.get(name)
            if raw is not None and raw.strip():
                try:
                    return int(raw.strip())
                except ValueError:
                    pass
            return default

        tessdata_raw = os.environ.get("TESSDATA_DIR") or os.environ.get("TESSDATA")
        tessdata_path = Path(tessdata_raw).expanduser() if tessdata_raw else None

        allow_remote = _env_truthy(os.environ.get("ALLOW_REMOTE"))
        restrict_host = not allow_remote

        kwargs: dict[str, Any] = {
            "host": os.environ.get("HOST", "127.0.0.1"),
            "port": _env_int("PORT", 8765),
            "tessdata": tessdata_path,
            "restrict_host": restrict_host,
            "max_upload_mb": _env_int("MAX_UPLOAD_MB", 200),
            "max_files": _env_int("MAX_FILES", 30),
            "ocr_workers": _env_int("OCR_WORKERS", 1),
            "job_ttl_seconds": _env_int("JOB_TTL_SECONDS", 2 * 60 * 60),
            "max_jobs_kept": _env_int("MAX_JOBS_KEPT", 20),
            "ocr_timeout_seconds": _env_int("OCR_TIMEOUT_SECONDS", 180),
            "max_tiff_frames": _env_int("MAX_TIFF_FRAMES", 500),
            "min_text_chars": _env_int("MIN_TEXT_CHARS", 20),
            "max_render_pixels": _env_int("MAX_RENDER_PIXELS", 120_000_000),
            "open_browser": not _env_truthy(os.environ.get("NO_BROWSER")),
            "trusted_proxies": _env_int("TRUSTED_PROXIES", 0),
        }
        kwargs.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**kwargs)
