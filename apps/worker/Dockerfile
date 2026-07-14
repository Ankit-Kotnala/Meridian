FROM python:3.13-slim@sha256:bffeb7bd6a85767587059c6ba23e1e9122078e3aa3fa836099171b9bb5a9bb00 AS runtime

ENV PATH="/workspace/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN python -m pip install --no-cache-dir "uv==0.11.21" \
    && addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app --home /nonexistent --no-create-home app

COPY --chown=app:app pyproject.toml uv.lock .python-version ./
COPY --chown=app:app apps/api/pyproject.toml apps/api/README.md ./apps/api/
COPY --chown=app:app apps/worker/pyproject.toml apps/worker/README.md ./apps/worker/
COPY --chown=app:app packages/backend/pyproject.toml packages/backend/README.md ./packages/backend/
COPY --chown=app:app apps/worker/src ./apps/worker/src
COPY --chown=app:app packages/backend/src ./packages/backend/src

RUN UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy uv sync \
      --frozen \
      --package careeros-worker \
      --no-dev \
      --no-editable \
    && uv cache clean \
    && /usr/local/bin/python -m pip uninstall --yes uv

USER app

HEALTHCHECK --interval=30s --timeout=8s --start-period=15s --retries=3 \
  CMD ["python", "-m", "careeros_worker.healthcheck"]

CMD ["celery", "--app", "careeros_worker.app:celery_app", "worker", "--loglevel=INFO"]
