"""Command-line entry point for the text extractor service."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path

from . import __version__
from .app import create_app
from .config import Settings
from .jobs import JobStore
from .ocr import tesseract_info


def _build_settings(args: argparse.Namespace) -> Settings:
    """Compose :class:`Settings` from CLI args + environment variables."""
    tessdata = args.tessdata or os.environ.get("TESSDATA_DIR")
    tessdata_path = Path(tessdata).expanduser() if tessdata else None
    restrict = not args.allow_remote and not _env_truthy("ALLOW_REMOTE")
    return Settings.from_env(
        host=args.host,
        port=args.port,
        tessdata=tessdata_path,
        restrict_host=restrict,
        max_upload_mb=args.max_upload_mb,
        max_files=args.max_files,
        open_browser=not args.no_browser,
    )


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="text-extractor",
        description="PDF & Image to Text — runs on your computer.",
    )
    p.add_argument("--host", default="127.0.0.1", help="address to listen on (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=8765, help="port to listen on (default: 8765)")
    p.add_argument("--tessdata", help="folder that contains *.traineddata files")
    p.add_argument("--no-browser", action="store_true", help="do not open the browser automatically")
    p.add_argument("--allow-remote", action="store_true",
                   help="allow non-localhost clients (also: ALLOW_REMOTE=1). "
                        "There is no password — only do this on a trusted network.")
    p.add_argument("--max-upload-mb", type=int, default=200, help="max upload size in MB (default: 200)")
    p.add_argument("--max-files", type=int, default=30, help="max files per job (default: 30)")
    p.add_argument("--version", action="version", version=f"text-extractor {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = _build_settings(args)

    if not settings.restrict_host:
        print(
            "WARNING: listening on a network address. Anyone who can reach it can use this app. "
            "There is no password.",
            file=sys.stderr,
        )

    installed, version, codes = tesseract_info(settings)
    if not installed:
        print(
            "Note: Tesseract was not found. PDFs that already contain text will work; "
            "scanned pages and images need Tesseract (see the README for install steps).",
            file=sys.stderr,
        )
    else:
        print(f"Tesseract {version}; languages: {', '.join(codes) or 'none'}")

    app = create_app(settings, job_store=JobStore(settings))
    host_for_url = "127.0.0.1" if args.host in ("0.0.0.0", "") else args.host
    url = f"http://{host_for_url}:{args.port}"
    print(f"Open {url} in your browser. Press Ctrl+C to stop.")

    if settings.open_browser:
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()

    try:
        app.run(host=args.host, port=args.port, threaded=True, debug=False)
    except OSError as exc:
        print(f"Could not start on port {args.port}: {exc}. Try --port 8766.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
