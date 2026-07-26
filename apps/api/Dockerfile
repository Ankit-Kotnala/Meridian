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
COPY --chown=10001:10001 apps/api/src ./apps/api/src
COPY --chown=10001:10001 packages/backend/src ./packages/backend/src
COPY --chown=10001:10001 packages/backend/alembic.ini ./packages/backend/alembic.ini
COPY --chown=10001:10001 packages/backend/alembic ./packages/backend/alembic

RUN UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy uv sync \
      --frozen \
      --package careeros-api \
      --no-dev \
      --no-editable \
    && uv cache clean \
    && /usr/local/bin/python -m pip uninstall --yes uv

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]

CMD ["python", "-m", "uvicorn", "careeros_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
