"""``GET /api/info`` — capability probe for the front-end."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from ..ocr import tesseract_info

bp = Blueprint("info", __name__, url_prefix="/api")


@bp.get("/info")
def info():
    settings = current_app.config["TEXT_EXTRACTOR_SETTINGS"]
    installed, version, codes = tesseract_info(settings)
    langs = [{"code": c, "name": settings.lang_names.get(c, c)} for c in codes]
    default = [c for c in ("eng", "ben") if c in codes] or codes[:1]
    return jsonify(
        {
            "tesseract": installed,
            "version": version,
            "languages": langs,
            "default": default,
            "max_files": settings.max_files,
            "max_upload_mb": settings.max_upload_mb,
            "extensions": sorted(settings.allowed_exts),
        }
    )
