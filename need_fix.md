# need_fix — Text_extractor

Security review 2026-10-14. Shared checklist and full context:
`../SECURITY_REVIEW.md`.

> **NOT REVIEWED.** Auto mode's shell was unavailable for most of this session,
> which made it impossible to list or grep this repo. No audit was performed
> and no code was changed. This is a checklist, not a findings list.

⚠️ **This repo is already public** at
`github.com/arafatsheikh098/Text-Extractor` (per `../git_push.md`), so unlike
most of its siblings a committed secret here is *already exposed* and must be
rotated, not just deleted.

## 1. Secrets — highest priority, because this is public

```bash
git ls-files | grep -iE '(\.env$|\.db$|\.sqlite3?$|\.pem$|\.key$|credential|token)'
git log --all --oneline -- .env
grep -rniE '(api[_-]?key|secret|token|password)[[:space:]]*=[[:space:]]*["'"'"'][^"'"'"']{8,}' \
  --exclude-dir=.git --exclude-dir=.venv .
```

If this tool calls a cloud OCR/vision API (Google Vision, AWS Textract, Azure,
or an LLM provider), that is exactly where a key tends to get hardcoded. A key
found in a public repo's history is compromised: **rotate it at the provider**,
then remove it from history.

## 2. Establish the layout first

The structure here was never inspected, so start by finding out what it is:

```bash
ls -A
find . -name '*.py' -not -path './.venv/*' -not -path './.git/*' | head -40
cat pyproject.toml requirements.txt 2>/dev/null
```

Then apply whichever applies: `../SECURITY_REVIEW.md` §4 in full if it turns
out to be a FastAPI web app like its siblings, or only items 1 and 11 (secrets,
pinning) if it is a CLI or library.

## 3. Untrusted document input — the core attack surface

A text extractor exists to be pointed at files the user did not author:

- **PDFs are hostile input.** Check which library is used. If it shells out to
  `pdftotext`/poppler or ImageMagick, confirm the filename is passed as an
  argument list and never interpolated into a shell string
  (`subprocess.run([...], shell=False)`). ImageMagick in particular has a long
  CVE history on crafted files.
- **XML-based formats** (`.docx`, `.xlsx`, `.odt`, SVG) are zip+XML. If parsed
  with `xml.etree` or `lxml` without hardening, they are vulnerable to XXE
  (local file disclosure, SSRF) and the "billion laughs" entity expansion.
  Use `defusedxml`, or disable entity resolution explicitly.
- **Zip/archive extraction.** `zipfile`/`tarfile` extraction without a member
  path check allows writing outside the target directory (`..`, absolute
  paths) — and zip bombs. Python 3.12's `filter="data"` for tarfiles.
- **Decompression bombs** on image input: Pillow only *warns* by default; set
  `Image.MAX_IMAGE_PIXELS` deliberately.
- **Resource limits.** A 10,000-page PDF or a deeply nested document should hit
  a timeout and page/size cap rather than consuming the host.
- **If a URL can be supplied** as the input source, that is SSRF: block
  loopback, link-local (`169.254.0.0/16`) and private ranges, and do not follow
  redirects blindly.

## 4. Output handling

- If extracted text is rendered to **HTML**, it is attacker-controlled content —
  confirm autoescaping is on. Document text is exactly the kind of input that
  carries `<script>`.
- If written to **CSV**, apply formula-injection escaping — see F12 in
  `../SECURITY_REVIEW.md`, where a sibling applied it to three of four columns.
- Confirm temp files are created with `tempfile` (0o600) and cleaned up, not
  written to a predictable path in `/tmp`.

## 5. Also

- Dependency pinning, per `CLAUDE.md`'s "Pin all versions", and check the
  parsing libraries for known CVEs — they are the ones that get exploited.
- Read any `AUDIT_REPORT.md` / `BLOCKERS.md` first.

## Then

```bash
.venv/bin/python -m pytest -q
```
