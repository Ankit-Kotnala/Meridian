FROM python:3.13-alpine3.24@sha256:42825e7ec3437b3bce923c237484eb23d32128476e18307d2f48951bf86f1db2 AS runtime

ENV PATH="/workspace/backend/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN python -m pip install --no-cache-dir "uv==0.11.21"

COPY --chown=10001:10001 backend/pyproject.toml backend/uv.lock backend/.python-version ./backend/
COPY --chown=10001:10001 backend/api/pyproject.toml backend/api/README.md ./backend/api/
COPY --chown=10001:10001 backend/worker/pyproject.toml backend/worker/README.md ./backend/worker/
COPY --chown=10001:10001 backend/core/pyproject.toml backend/core/README.md ./backend/core/
COPY --chown=10001:10001 backend/worker/src ./backend/worker/src
COPY --chown=10001:10001 backend/worker/docker-entrypoint.sh ./backend/worker/docker-entrypoint.sh
COPY --chown=10001:10001 backend/core/src ./backend/core/src

RUN chmod 0555 ./backend/worker/docker-entrypoint.sh

RUN UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy uv sync \
      --project backend \
      --frozen \
      --package rezumi-worker \
      --no-dev \
      --no-editable \
    && uv cache clean \
    && /usr/local/bin/python -m pip uninstall --yes uv

USER 10001:10001

EXPOSE 8000

CMD ["/workspace/backend/worker/docker-entrypoint.sh"]
