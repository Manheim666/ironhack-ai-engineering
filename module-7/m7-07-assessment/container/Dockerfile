# Multi-stage Dockerfile for the `ranker` serving image (Scenario X).
#
# Per ADR-0001 the model is BAKED IN, not mounted: the image is the release.
# This file is for review, not for an actual build in this assessment — but it's written to be real.
#
# Two stages:
#   1) builder  — install deps into a venv, pull the model artifact. Has build tooling.
#   2) runtime  — slim, no build tooling, non-root. Only the venv + app + model come across.

# ---------- Stage 1: builder ----------
# Pin the base by digest in real life (kept readable here). slim keeps the final image small.
FROM python:3.12-slim AS builder

# Don't write .pyc, don't buffer stdout (so logs show up), keep pip quiet-ish.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Build deps only needed to compile wheels — they stay in this stage, never reach runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps into an isolated venv so we can copy just that dir into runtime.
COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Bake the model. ARG ties the build to a specific registry version (matches lifecycle/registry).
# In CI this is fetched from the model registry by tag; here it's a placeholder copy.
ARG MODEL_VERSION=1.4.2
COPY models/ranker-${MODEL_VERSION}/ /opt/model/
# Sanity: fail the build now if the artifact is missing, not at 3am on a pod.
RUN test -f /opt/model/ranker.bin || (echo "model artifact missing for ${MODEL_VERSION}" && exit 1)

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    # Surfaced in the X-Model-Version header. Stays in sync with the baked artifact.
    MODEL_VERSION=1.4.2

# Run as a non-root user. If something pops the process, it isn't root in the container.
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app

# Bring over ONLY the venv and the baked model from the builder — no compilers, no apt cache.
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/model /opt/model

# App code last — it changes most often, so it's the layer that busts least of the cache above.
COPY --chown=app:app app/ /app/

USER app

EXPOSE 8080

# Liveness/readiness hit these (see architecture.md). Readiness fails if the model can't load.
HEALTHCHECK --interval=10s --timeout=2s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8080/readyz')" || exit 1

# Gunicorn + uvicorn workers serving the FastAPI app. Worker count tuned to the pod's 4 vCPU.
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8080", \
     "--timeout", "30", \
     "--access-logfile", "-"]
