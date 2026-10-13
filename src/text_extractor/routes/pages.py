"""The HTML page and favicon."""

from __future__ import annotations

import secrets

from flask import Blueprint, Response, render_template

bp = Blueprint("pages", __name__)


@bp.get("/")
def index() -> Response:
    nonce = secrets.token_urlsafe(16)
    html = render_template("index.html", nonce=nonce)
    resp = Response(html, mimetype="text/html")
    # 'self' is included for the external /static/app.js and style.css; the
    # nonce alone would block them. The page still has no inline script or
    # style, and no remote origins are allowed.
    resp.headers["Content-Security-Policy"] = (
        f"default-src 'none'; script-src 'self' 'nonce-{nonce}'; "
        f"style-src 'self' 'nonce-{nonce}'; "
        "connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'"
    )
    return resp


@bp.get("/favicon.ico")
def favicon() -> Response:
    return Response(status=204)
