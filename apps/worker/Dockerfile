FROM python:3.13-slim AS runtime

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN python -m pip install --no-cache-dir "uv==0.11.7" \
    && addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app --home /nonexistent --no-create-home app

COPY --chown=app:app pyproject.toml uv.lock README.md ./
COPY --chown=app:app src ./src

RUN uv sync --frozen --no-dev --no-editable \
    && uv cache clean \
    && install -d -o app -g app "${UV_CACHE_DIR}"

ENV UV_NO_SYNC=1

USER app

HEALTHCHECK --interval=30s --timeout=8s --start-period=15s --retries=3 \
  CMD ["python", "-m", "careeros_worker.healthcheck"]

CMD ["celery", "--app", "careeros_worker.app:celery_app", "worker", "--loglevel=INFO"]
