"""Cross-cutting security middleware: host guard, origin check, security headers."""

from __future__ import annotations

import re

from flask import Blueprint, Flask, Response, abort, jsonify, request

from ..config import Settings

bp = Blueprint("security", __name__)


def install(app: Flask, settings: Settings) -> None:
    """Wire :func:`before_request` and :func:`after_request` on ``app``."""
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_bytes

    @app.before_request
    def _guard() -> None:  # type: ignore[no-redef]
        if settings.restrict_host and not settings.is_local_host(request.host):
            abort(403)  # blocks DNS-rebinding attacks against the local app
        origin = request.headers.get("Origin")
        if (
            origin
            and request.method not in ("GET", "HEAD", "OPTIONS")
            and re.sub(r"^https?://", "", origin) != request.host
        ):
            abort(403)

    @app.after_request
    def _headers(resp: Response) -> Response:  # type: ignore[no-redef]
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(413)
    def _too_large(_):
        return jsonify({"error": f"These files are too large. The limit for one upload is {settings.max_upload_mb} MB."}), 413

    @app.errorhandler(403)
    def _forbidden(_):
        return Response("Forbidden", status=403, mimetype="text/plain")

    @app.errorhandler(404)
    def _not_found(err):
        if request.path.startswith("/api/"):
            return jsonify({"error": getattr(err, "description", "Not found.")}), 404
        return Response("Not found", status=404, mimetype="text/plain")
