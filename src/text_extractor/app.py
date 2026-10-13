"""Flask app factory.

The factory is what makes this package testable: each call returns a fresh
:class:`flask.Flask` with its own :class:`JobStore` and a configurable
:class:`concurrent.futures.Executor`. Tests pass a synchronous executor (or
even just ``None`` and call :func:`jobs.run_job` directly) so they can
assert on job state without timing flakiness.
"""

from __future__ import annotations

import logging
from concurrent.futures import Executor, ThreadPoolExecutor
from typing import Any

from flask import Flask

from .config import Settings
from .jobs import JobStore
from .routes import info, pages, security
from .routes import jobs as jobs_routes


def create_app(
    settings: Settings | None = None,
    *,
    executor: Executor | None = None,
    job_store: JobStore | None = None,
    test_config: dict[str, Any] | None = None,
) -> Flask:
    """Build a Flask app. Pass overrides for tests."""
    settings = settings or Settings()
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config["TEXT_EXTRACTOR_SETTINGS"] = settings
    app.config["TEXT_EXTRACTOR_EXECUTOR"] = executor or ThreadPoolExecutor(
        max_workers=settings.ocr_workers
    )
    app.config["TEXT_EXTRACTOR_JOB_STORE"] = job_store or JobStore(settings)
    if test_config:
        app.config.update(test_config)

    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    if settings.trusted_proxies > 0:
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(  # type: ignore[method-assign]
            app.wsgi_app,
            x_for=settings.trusted_proxies,
            x_proto=settings.trusted_proxies,
            x_host=settings.trusted_proxies,
            x_prefix=settings.trusted_proxies,
        )

    security.install(app, settings)
    app.register_blueprint(pages.bp)
    app.register_blueprint(info.bp)
    app.register_blueprint(jobs_routes.bp)
    return app


__all__ = ["create_app"]
