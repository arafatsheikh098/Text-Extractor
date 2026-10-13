"""HTTP-level tests for the Flask blueprints."""

from __future__ import annotations

import io
import json
from unittest.mock import patch

from PIL import Image


# ---------------------------------------------------------------- /api/info
def test_info_endpoint_shape(client, settings) -> None:
    with patch("text_extractor.routes.info.tesseract_info",
               return_value=(True, "5.3.0", ["ben", "eng"])):
        res = client.get("/api/info")
    assert res.status_code == 200
    data = res.get_json()
    assert data["tesseract"] is True
    assert data["version"] == "5.3.0"
    assert {"code": "ben", "name": "Bangla"} in data["languages"]
    assert data["max_files"] == settings.max_files
    assert data["max_upload_mb"] == settings.max_upload_mb
    assert data["extensions"]  # non-empty


# ---------------------------------------------------------------- host guard
def test_non_localhost_blocked_when_restricted(client) -> None:
    # werkzeug's test client sets Host to localhost by default; simulate a
    # remote host by passing the base_url or headers. The before_request
    # guard inspects request.host.
    res = client.get("/api/info", headers={"Host": "evil.example.com"})
    assert res.status_code == 403


def test_localhost_allowed(client) -> None:
    with patch("text_extractor.routes.info.tesseract_info",
               return_value=(True, "5.3.0", ["eng"])):
        res = client.get("/api/info", headers={"Host": "127.0.0.1:8765"})
    assert res.status_code == 200


# ---------------------------------------------------------------- /api/jobs POST
def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color="white").save(buf, format="PNG")
    return buf.getvalue()


def test_create_job_rejects_empty(client) -> None:
    res = client.post("/api/jobs", data={"lang": "eng"}, content_type="multipart/form-data")
    assert res.status_code == 400
    assert "at least one" in res.get_json()["error"]


def test_create_job_rejects_unsupported_extension(client) -> None:
    data = {"files": [(io.BytesIO(b"hello"), "thing.txt")], "lang": "eng"}
    res = client.post(
        "/api/jobs",
        data=data,
        content_type="multipart/form-data",
    )
    assert res.status_code == 400
    assert "not a supported file type" in res.get_json()["error"]


def test_create_job_rejects_unknown_language(client) -> None:
    with patch("text_extractor.routes.jobs._installed_langs", return_value=(True, "5.0", ["eng"])):
        data = {"files": [(io.BytesIO(_png_bytes()), "x.png")], "lang": "klingon"}
        res = client.post("/api/jobs", data=data, content_type="multipart/form-data")
    assert res.status_code == 400
    assert "language" in res.get_json()["error"].lower()


def test_create_job_accepts_png_and_marks_done(client, tmp_path) -> None:
    with patch("text_extractor.routes.jobs._installed_langs", return_value=(True, "5.0", ["eng"])), \
         patch("text_extractor.routes.jobs.run_job") as m_run:
        data = {"files": [(io.BytesIO(_png_bytes()), "x.png")], "lang": "eng", "dpi": "300"}
        res = client.post("/api/jobs", data=data, content_type="multipart/form-data")
    assert res.status_code == 201
    body = res.get_json()
    assert "job_id" in body
    m_run.assert_called_once()
    call_args = m_run.call_args.args
    job = call_args[0]
    assert job.options["lang"] == "eng"
    assert job.options["dpi"] == 300
    assert job.options["force_ocr"] is False
    assert len(job.files) == 1
    assert job.files[0].ext == ".png"


# ---------------------------------------------------------------- /api/zip
def test_zip_dedupes_and_writes(client) -> None:
    payload = {"files": [
        {"name": "a.pdf", "text": "one"},
        {"name": "a.pdf", "text": "two"},
    ]}
    res = client.post("/api/zip", data=json.dumps(payload), content_type="application/json")
    assert res.status_code == 200
    assert res.mimetype == "application/zip"
    import zipfile
    with zipfile.ZipFile(io.BytesIO(res.data)) as zf:
        names = sorted(zf.namelist())
    assert names == ["a.txt", "a_2.txt"]


def test_zip_rejects_non_string_text(client) -> None:
    res = client.post("/api/zip", data=json.dumps({"files": [{"name": "x", "text": 12}]}),
                      content_type="application/json")
    assert res.status_code == 400


# ---------------------------------------------------------------- / (page)
def test_index_renders(client) -> None:
    res = client.get("/")
    assert res.status_code == 200
    assert b"PDF" in res.data
    assert "Content-Security-Policy" in res.headers
    csp = res.headers["Content-Security-Policy"]
    assert "default-src 'none'" in csp
    assert "nonce-" in csp
    assert b"static" in res.data  # link to the external stylesheet
    assert b"nonce=" in res.data  # CSP nonce applied to the <script> tag


# ---------------------------------------------------------------- job lifecycle routes
def test_job_status_and_text_and_cancel(client) -> None:
    from text_extractor.jobs import STATUS_DONE, FileState, Job

    fs = FileState(id="f0", name="sample.png", path="/tmp/fake", ext=".png", status=STATUS_DONE, text="extracted result")
    job = Job(id="testjob123", options={}, files=[fs], workdir="/tmp/fake")
    client.application.config["TEXT_EXTRACTOR_JOB_STORE"].add(job)

    # Status
    res = client.get("/api/jobs/testjob123")
    assert res.status_code == 200
    assert res.get_json()["id"] == "testjob123"

    # Text
    res_text = client.get("/api/jobs/testjob123/files/f0/text")
    assert res_text.status_code == 200
    assert res_text.data.decode("utf-8") == "extracted result"

    # Cancel
    res_cancel = client.post("/api/jobs/testjob123/cancel")
    assert res_cancel.status_code == 200
    assert res_cancel.get_json()["ok"] is True
    assert job.cancel.is_set()


def test_job_not_found(client) -> None:
    res = client.get("/api/jobs/nonexistent")
    assert res.status_code == 404

