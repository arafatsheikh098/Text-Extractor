"""Allow ``python -m text_extractor`` to launch the server."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
