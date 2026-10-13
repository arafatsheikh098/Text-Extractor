# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-13

### Added
- **Core Text Extraction**:
  - Direct digital text extraction for born-digital PDFs via PyMuPDF.
  - Optical Character Recognition (OCR) fallback for scanned PDFs and image files via Tesseract.
  - Support for multi-language OCR (English, Bangla, Hindi, Urdu, Arabic, Assamese, Nepali, French, German, Spanish).
  - Multi-frame TIFF and batch image processing.
  - Page marker formatting option (`--- Page N ---`).
  - Batch zip export of extracted `.txt` files.
- **Security & Sandboxing**:
  - DNS-rebinding host guard (`Settings.restrict_host`).
  - Cross-Origin request validation on state-changing endpoints.
  - Pixel decompression bomb limits (`MAX_RENDER_PIXELS`).
  - Non-root container execution (`useradd app`).
  - Reverse proxy support via `ProxyFix` middleware (`TRUSTED_PROXIES`).
- **Configuration & Deployment**:
  - `Settings.from_env()` enabling full environment variable configuration.
  - Multi-threaded Gunicorn WSGI configuration avoiding multi-worker in-memory split-brain.
  - Dockerfile with Debian Bookworm, Python 3.12, and preinstalled language packs.
  - Docker Compose configuration with healthchecks.
  - Render (`render.yaml`) and Fly.io (`fly.toml`) 1-click cloud deployment definitions.
  - `.env.example` template with comprehensive variable documentation.
- **GitHub & CI/CD**:
  - GitHub Actions CI workflow supporting Python 3.10 through 3.13.
  - GitHub Container Registry (GHCR) publishing workflow (`docker-publish.yml`).
  - Dependabot automated security dependency tracking.
  - Issue templates (bug report, feature request) and Pull Request template.
  - Community documents (`CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`).
