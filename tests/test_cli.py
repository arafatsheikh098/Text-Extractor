"""Unit tests for :mod:`text_extractor.cli`."""

from __future__ import annotations

from text_extractor.cli import _build_parser, _build_settings


def test_cli_parser_defaults() -> None:
    parser = _build_parser()
    args = parser.parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8765
    assert args.max_upload_mb == 200
    assert args.max_files == 30
    assert args.allow_remote is False
    assert args.no_browser is False


def test_cli_parser_custom_flags() -> None:
    parser = _build_parser()
    args = parser.parse_args([
        "--host", "0.0.0.0",
        "--port", "9999",
        "--max-upload-mb", "50",
        "--max-files", "10",
        "--allow-remote",
        "--no-browser",
    ])
    assert args.host == "0.0.0.0"
    assert args.port == 9999
    assert args.max_upload_mb == 50
    assert args.max_files == 10
    assert args.allow_remote is True
    assert args.no_browser is True


def test_build_settings_from_cli_args() -> None:
    parser = _build_parser()
    args = parser.parse_args(["--port", "8888", "--allow-remote", "--no-browser"])
    settings = _build_settings(args)
    assert settings.port == 8888
    assert settings.restrict_host is False
    assert settings.open_browser is False
