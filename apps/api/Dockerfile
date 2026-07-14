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

COPY --chown=app:app pyproject.toml uv.lock README.md alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app src ./src

RUN uv sync --frozen --no-dev --no-editable \
    && uv cache clean \
    && install -d -o app -g app "${UV_CACHE_DIR}"

ENV UV_NO_SYNC=1

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]

CMD ["uvicorn", "careeros_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
