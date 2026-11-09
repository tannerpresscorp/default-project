# syntax=docker/dockerfile:1
# Shared image for the FastAPI control plane and the Temporal worker. The
# entrypoint is supplied by the deployment (uvicorn or the worker module).
# Base image is pinned by digest so a rebuild cannot silently change runtimes.
FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
COPY requirements-platform.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-compile -r requirements-platform.txt

FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    HOME=/tmp

RUN groupadd --gid 10001 platform \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin platform

WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY alembic.ini ./
COPY apps ./apps
COPY packages ./packages

# The root filesystem can stay read-only; only /tmp is expected to be writable.
USER 10001:10001
EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health/live', timeout=2)"]

CMD ["python", "-m", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8001"]
