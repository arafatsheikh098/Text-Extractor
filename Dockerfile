# syntax=docker/dockerfile:1.6
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Tesseract + the language packs the UI exposes. Add or remove languages
# here to match your users; the corresponding *.traineddata files must
# exist under /usr/share/tesseract-ocr/*/tessdata/.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-ben \
        tesseract-ocr-hin \
        tesseract-ocr-urd \
        tesseract-ocr-ara \
        tesseract-ocr-asm \
        tesseract-ocr-nep \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so Docker can cache the layer when only source
# changes.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# Drop privileges
RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8765

# Use 1 worker with multiple threads: the in-memory JobStore is process-local.
# Multi-threading handles concurrent requests while maintaining a single shared job store.
# Override via GUNICORN_CMD_ARGS if needed.
ENV GUNICORN_CMD_ARGS="--timeout 180"
CMD ["gunicorn", "-w", "1", "-k", "gthread", "--threads", "4", \
     "-b", "0.0.0.0:8765", "text_extractor.wsgi:app"]

