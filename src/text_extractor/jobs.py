"""In-memory job and file state, plus the background runner.

A "job" is one upload: a set of files, a set of options, and a single
executor that walks the files in order. State lives in module-level globals
inside the Flask app, not in a database — the README is explicit that jobs
are gone when the process restarts.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
import traceback
from collections.abc import Mapping
from concurrent.futures import Executor
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from .config import Settings
from .errors import Cancelled, UserFacingError
from .ocr import describe_error
from .processing import process_image, process_pdf

# Status values used in the JSON response. Kept as plain strings so they
# round-trip through jsonify without a custom encoder.
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"


@dataclass
class FileState:
    """Mutable progress record for one uploaded file."""

    id: str
    name: str
    path: str
    ext: str
    status: str = STATUS_QUEUED
    pages_total: int = 0
    pages_done: int = 0
    text_pages: int = 0
    ocr_pages: int = 0
    text: str = ""
    error: str | None = None
    warning: str | None = None

    def public(self) -> dict[str, Any]:
        """The JSON-safe view of this file, sent to the browser."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "pages_total": self.pages_total,
            "pages_done": self.pages_done,
            "text_pages": self.text_pages,
            "ocr_pages": self.ocr_pages,
            "chars": len(self.text) if self.status == STATUS_DONE else 0,
            "error": self.error,
            "warning": self.warning,
        }


@dataclass
class Job:
    """One upload, one executor task."""

    id: str
    options: Mapping[str, Any]
    files: list[FileState]
    workdir: str
    status: str = STATUS_QUEUED
    created: float = field(default_factory=time.time)
    finished: float | None = None
    cancel: threading.Event = field(default_factory=threading.Event)

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "status": self.status, "files": [f.public() for f in self.files]}


class JobStore:
    """Thread-safe map of :class:`Job` keyed by id, with TTL-based pruning."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def add(self, job: Job) -> None:
        with self._lock:
            # Prune before and after the insert: prune-before keeps the cap
            # honest when the new job itself is past TTL or otherwise
            # uninteresting, and prune-after runs the cap one more time in
            # case the insert pushed us over the limit.
            self._prune_locked_inner()
            self._jobs[job.id] = job
            self._prune_locked_inner()

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def all(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def _prune_locked_inner(self) -> None:
        """The actual pruning logic. Caller must hold ``self._lock``."""
        now = time.time()
        expired = [j.id for j in self._jobs.values() if j.finished and now - j.finished > self._settings.job_ttl_seconds]
        for jid in expired:
            self._jobs.pop(jid, None)
        if len(self._jobs) > self._settings.max_jobs_kept:
            finished = sorted((j for j in self._jobs.values() if j.finished), key=lambda j: j.finished)
            for j in finished[: len(self._jobs) - self._settings.max_jobs_kept]:
                self._jobs.pop(j.id, None)

    def prune(self) -> None:
        """Public alias used by the route layer and tests."""
        with self._lock:
            self._prune_locked_inner()


# --------------------------------------------------------------------------- runner
class _ProcessContextAdapter:
    """Adapts a :class:`Job` to the :class:`ProcessContext` protocol."""

    def __init__(self, job: Job) -> None:
        self.options = job.options
        self.cancel = job.cancel


def run_job(job: Job, settings: Settings) -> None:
    """Walk every file in a job, in order, on the calling thread."""
    job.status = STATUS_RUNNING
    try:
        for fs in job.files:
            if job.cancel.is_set():
                fs.status = STATUS_CANCELLED
                continue
            fs.status = STATUS_RUNNING
            ctx = _ProcessContextAdapter(job)
            try:
                if fs.ext == ".pdf":
                    process_pdf(fs, ctx, settings)
                else:
                    process_image(fs, ctx, settings)
                fs.status = STATUS_DONE
                if not fs.text:
                    fs.warning = (
                        "No text was found. Try a higher scan quality or a different language."
                    )
            except Cancelled:
                fs.status = STATUS_CANCELLED
            except Exception as exc:
                fs.status = STATUS_FAILED
                fs.error = describe_error(exc, settings)
                if not isinstance(exc, UserFacingError):
                    traceback.print_exc()
            finally:
                with suppress(OSError):
                    os.unlink(fs.path)
    finally:
        job.status = STATUS_CANCELLED if job.cancel.is_set() else STATUS_DONE
        job.finished = time.time()
        shutil.rmtree(job.workdir, ignore_errors=True)


__all__ = [
    "STATUS_CANCELLED",
    "STATUS_DONE",
    "STATUS_FAILED",
    "STATUS_QUEUED",
    "STATUS_RUNNING",
    "Executor",
    "FileState",
    "Job",
    "JobStore",
    "process_image",
    "process_pdf",
    "run_job",
]
