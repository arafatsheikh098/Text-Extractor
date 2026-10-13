"""Unit tests for :mod:`text_extractor.jobs`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PIL import Image

from text_extractor.config import Settings
from text_extractor.errors import UserFacingError
from text_extractor.jobs import (
    FileState,
    Job,
    JobStore,
    run_job,
)


def _png(path: Path) -> Path:
    Image.new("RGB", (8, 8), color="white").save(path, format="PNG")
    return path


def test_run_job_marks_done(tmp_path: Path, settings: Settings) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    p = workdir / "f0.png"
    _png(p)
    fs = FileState(id="f0", name="f0.png", path=str(p), ext=".png")
    job = Job(
        id="j1",
        options={"lang": "eng", "dpi": 300, "force_ocr": False, "page_markers": False},
        files=[fs],
        workdir=str(workdir),
    )
    with patch("text_extractor.jobs.process_image", return_value=None) as m:
        run_job(job, settings)
    m.assert_called_once()
    assert fs.status == "done"
    assert job.status == "done"
    assert job.finished is not None
    assert not p.exists()  # uploaded copy cleaned up
    assert not workdir.exists()  # workdir cleaned up


def test_run_job_marks_cancelled(tmp_path: Path, settings: Settings) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    p = workdir / "f0.png"
    _png(p)
    fs = FileState(id="f0", name="f0.png", path=str(p), ext=".png")
    job = Job(
        id="j1",
        options={"lang": "eng", "dpi": 300, "force_ocr": False, "page_markers": False},
        files=[fs],
        workdir=str(workdir),
    )
    job.cancel.set()
    with patch("text_extractor.jobs.process_image", return_value=None):
        run_job(job, settings)
    assert fs.status == "cancelled"
    assert job.status == "cancelled"


def test_run_job_marks_failed(tmp_path: Path, settings: Settings) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    p = workdir / "f0.png"
    _png(p)
    fs = FileState(id="f0", name="f0.png", path=str(p), ext=".png")
    job = Job(
        id="j1",
        options={"lang": "eng", "dpi": 300, "force_ocr": False, "page_markers": False},
        files=[fs],
        workdir=str(workdir),
    )

    def boom(*_a, **_kw):
        raise UserFacingError("boom")

    with patch("text_extractor.jobs.process_image", side_effect=boom):
        run_job(job, settings)
    assert fs.status == "failed"
    assert fs.error == "boom"
    assert job.status == "done"


def test_job_store_prune(settings: Settings) -> None:
    # Use a short TTL so we can build a job that's clearly past it without
    # hitting the floating-point zero truthiness trap.
    import time
    s = Settings(job_ttl_seconds=10)
    store = JobStore(s)
    j1 = Job(id="a", options={}, files=[], workdir="/tmp/whatever")
    # j1 is *not yet* finished — it's a fresh queued job, so the before-add
    # prune keeps it.
    j2 = Job(id="b", options={}, files=[], workdir="/tmp/whatever")
    j2.finished = time.time() - 3600  # one hour ago, well past 10s TTL
    store.add(j1)
    assert {j.id for j in store.all()} == {"a"}
    store.add(j2)  # b is past TTL; the after-add prune should evict it
    assert {j.id for j in store.all()} == {"a"}


def test_job_store_caps_size(settings: Settings) -> None:
    import time
    small = Settings(max_jobs_kept=2, job_ttl_seconds=10_000)
    store = JobStore(small)
    base = time.time()
    for i in range(5):
        j = Job(id=f"j{i}", options={}, files=[], workdir="/tmp/x")
        # +1.0 so 0 doesn't trip the truthiness check; all well within TTL.
        j.finished = base + float(i) + 1.0
        store.add(j)
    assert len(store.all()) == 2
    assert {j.id for j in store.all()} == {"j3", "j4"}
