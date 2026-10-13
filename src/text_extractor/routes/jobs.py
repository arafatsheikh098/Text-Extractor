"""Job management endpoints: create, status, fetch text, cancel, zip."""

from __future__ import annotations

import io
import os
import re
import shutil
import tempfile
import zipfile
from concurrent.futures import Executor
from pathlib import Path

from flask import Blueprint, Response, abort, current_app, jsonify, request, send_file

from ..config import Settings
from ..errors import UserFacingError
from ..jobs import (
    STATUS_DONE,
    FileState,
    Job,
    JobStore,
    run_job,
)

bp = Blueprint("jobs", __name__, url_prefix="/api")


# ---------------------------------------------------------------- helpers
def _settings() -> Settings:
    return current_app.config["TEXT_EXTRACTOR_SETTINGS"]


def _store() -> JobStore:
    return current_app.config["TEXT_EXTRACTOR_JOB_STORE"]


def _executor() -> Executor:
    return current_app.config["TEXT_EXTRACTOR_EXECUTOR"]


def _get_job_or_404(jid: str) -> Job:
    job = _store().get(jid)
    if job is None:
        abort(404, description="This job no longer exists. Extract the files again.")
    return job


def _api_error(message: str, status: int) -> tuple[Response, int]:
    return jsonify({"error": message}), status


def _safe_stem(name: str, fallback: str = "text") -> str:
    stem = Path(name).stem if name else fallback
    stem = re.sub(r"[\x00-\x1f\\/:*?\"<>|]", "_", stem).strip(" .")
    return stem[:120] or fallback


# ---------------------------------------------------------------- create
@bp.post("/jobs")
def create_job():
    settings = _settings()
    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return _api_error("Choose at least one PDF or image.", 400)
    if len(files) > settings.max_files:
        return _api_error(f"Choose at most {settings.max_files} files at a time.", 400)

    _, _, codes = _installed_langs()
    lang_tokens = [t for t in request.form.get("lang", "").split("+") if t]
    if lang_tokens and not set(lang_tokens) <= set(codes):
        return _api_error("One of the selected languages is not installed.", 400)
    lang = "+".join(lang_tokens) or ("eng" if "eng" in codes else "+".join(codes[:1]))

    try:
        dpi = int(request.form.get("dpi", settings.default_dpi))
    except ValueError:
        dpi = settings.default_dpi
    if dpi not in settings.dpi_choices:
        dpi = settings.default_dpi

    options = {
        "lang": lang,
        "dpi": dpi,
        "force_ocr": request.form.get("force_ocr") == "1",
        "page_markers": request.form.get("page_markers") == "1",
    }

    workdir = tempfile.mkdtemp(prefix="textextract_")
    states: list[FileState] = []
    try:
        for idx, up in enumerate(files):
            ext = Path(up.filename).suffix.lower()
            if ext not in settings.allowed_exts:
                raise UserFacingError(
                    f"\u201c{up.filename}\u201d is not a supported file type. "
                    "Use PDF, PNG, JPG, TIFF, BMP, WebP or GIF."
                )
            path = os.path.join(workdir, f"{idx}{ext}")
            up.save(path)
            states.append(FileState(id=f"f{idx}", name=up.filename, path=path, ext=ext))
    except UserFacingError as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        return _api_error(str(exc), 400)
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise

    job = Job(id=_new_job_id(), options=options, files=states, workdir=workdir)
    _store().add(job)
    _executor().submit(run_job, job, settings)
    return jsonify({"job_id": job.id}), 201


def _new_job_id() -> str:
    import uuid

    return uuid.uuid4().hex


def _installed_langs() -> tuple[bool, str | None, list[str]]:
    from ..ocr import tesseract_info

    return tesseract_info(_settings())


# ---------------------------------------------------------------- read
@bp.get("/jobs/<jid>")
def job_status(jid: str):
    return jsonify(_get_job_or_404(jid).public())


@bp.get("/jobs/<jid>/files/<fid>/text")
def file_text(jid: str, fid: str):
    job = _get_job_or_404(jid)
    fs = next((f for f in job.files if f.id == fid), None)
    if fs is None or fs.status != STATUS_DONE:
        abort(404, description="This text is not available.")
    return Response(fs.text, mimetype="text/plain; charset=utf-8")


@bp.post("/jobs/<jid>/cancel")
def cancel_job(jid: str):
    _get_job_or_404(jid).cancel.set()
    return jsonify({"ok": True})


# ---------------------------------------------------------------- zip
@bp.post("/zip")
def make_zip():
    data = request.get_json(silent=True) or {}
    items = data.get("files")
    if not isinstance(items, list) or not items or len(items) > 100:
        return _api_error("Nothing to put in the zip file.", 400)
    buffer = io.BytesIO()
    used: set[str] = set()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for it in items:
            if not isinstance(it, dict) or not isinstance(it.get("text"), str):
                return _api_error("Invalid file list.", 400)
            stem = _safe_stem(str(it.get("name", "")))
            candidate, n = stem, 2
            while candidate.lower() in used:
                candidate, n = f"{stem}_{n}", n + 1
            used.add(candidate.lower())
            zf.writestr(candidate + ".txt", it["text"].encode("utf-8"))
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name="extracted-text.zip",
    )
