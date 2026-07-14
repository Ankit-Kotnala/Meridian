FROM python:3.13-slim@sha256:bffeb7bd6a85767587059c6ba23e1e9122078e3aa3fa836099171b9bb5a9bb00 AS runtime

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN python -m pip install --no-cache-dir "uv==0.11.21" \
    && addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app --home /nonexistent --no-create-home app

COPY --chown=app:app pyproject.toml uv.lock README.md alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app src ./src

RUN UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy uv sync --frozen --no-dev --no-editable \
    && uv cache clean \
    && /usr/local/bin/python -m pip uninstall --yes uv

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]

CMD ["uvicorn", "careeros_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
