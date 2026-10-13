# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Text Extractor, please do not file a public issue on GitHub. Instead, report it privately to the maintainers:

- **Email**: [arafat.csecu@gmail.com](mailto:arafat.csecu@gmail.com)
- Please include steps to reproduce, the impacted version, and any relevant proof-of-concept payloads.

You should receive an initial acknowledgment within 48 hours.

## Security Architecture & Threat Model

1. **Host Guard (DNS-Rebinding Protection)**:
   By default, Text Extractor only binds to `127.0.0.1` and actively inspects the HTTP `Host` header against known local loopback aliases. Requests with arbitrary hostnames are rejected with `403 Forbidden`.

2. **Remote Exposure (`ALLOW_REMOTE=1`)**:
   Setting `ALLOW_REMOTE=1` disables localhost host filtering. **The application contains no built-in user authentication or authorization.** If deploying to a network or public domain, you must place the application behind a reverse proxy (e.g. Nginx, Caddy, Cloudflare Access, Authelia) providing HTTPS and authentication.

3. **Origin & CSRF Checks**:
   State-changing requests (`POST`) verify the HTTP `Origin` header to prevent cross-site request forgery from malicious browser contexts.

4. **Upload Hardening**:
   - File uploads are validated by extension and processed within isolated temporary directories.
   - Decompression bomb protections (Pillow max pixel limits) prevent memory exhaustion from zip-bombs or crafted image headers.
   - Upload sizes are strictly capped (default 200MB, configurable via `MAX_UPLOAD_MB`).
