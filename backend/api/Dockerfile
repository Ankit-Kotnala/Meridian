FROM python:3.14-alpine3.24@sha256:9e9fde4d32eedce0b661d9ab91e826b62dddf28e928c230ec55f1866cac66b01 AS runtime

ENV PATH="/workspace/backend/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN python -m pip install --no-cache-dir "uv==0.11.21"

COPY --chown=10001:10001 backend/pyproject.toml backend/uv.lock backend/.python-version ./backend/
COPY --chown=10001:10001 backend/api/pyproject.toml backend/api/README.md ./backend/api/
COPY --chown=10001:10001 backend/worker/pyproject.toml backend/worker/README.md ./backend/worker/
COPY --chown=10001:10001 backend/core/pyproject.toml backend/core/README.md ./backend/core/
COPY --chown=10001:10001 backend/api/src ./backend/api/src
COPY --chown=10001:10001 backend/core/src ./backend/core/src
COPY --chown=10001:10001 backend/core/alembic.ini ./backend/core/alembic.ini
COPY --chown=10001:10001 backend/core/alembic ./backend/core/alembic

RUN UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy uv sync \
      --project backend \
      --frozen \
      --package rezumi-api \
      --no-dev \
      --no-editable \
    && uv cache clean \
    && /usr/local/bin/python -m pip uninstall --yes uv

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]

CMD ["python", "-m", "uvicorn", "rezumi_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
