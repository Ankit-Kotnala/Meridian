FROM python:3.13-alpine3.24@sha256:399babc8b49529dabfd9c922f2b5eea81d611e4512e3ed250d75bd2e7683f4b0 AS runtime

ENV PATH="/workspace/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN python -m pip install --no-cache-dir "uv==0.11.21"

COPY --chown=10001:10001 pyproject.toml uv.lock .python-version ./
COPY --chown=10001:10001 apps/api/pyproject.toml apps/api/README.md ./apps/api/
COPY --chown=10001:10001 apps/worker/pyproject.toml apps/worker/README.md ./apps/worker/
COPY --chown=10001:10001 packages/backend/pyproject.toml packages/backend/README.md ./packages/backend/
COPY --chown=10001:10001 apps/worker/src ./apps/worker/src
COPY --chown=10001:10001 packages/backend/src ./packages/backend/src

RUN UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy uv sync \
      --frozen \
      --package careeros-worker \
      --no-dev \
      --no-editable \
    && uv cache clean \
    && /usr/local/bin/python -m pip uninstall --yes uv

USER 10001:10001

HEALTHCHECK --interval=30s --timeout=8s --start-period=15s --retries=3 \
  CMD ["python", "-m", "careeros_worker.healthcheck"]

CMD ["celery", "--app", "careeros_worker.app:celery_app", "worker", "--loglevel=INFO", "--queues=default,resume-health,resume-builder,career-record,maintenance"]
