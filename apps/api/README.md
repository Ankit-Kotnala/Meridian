# CareerOS API

Phase 0 FastAPI service foundation. It intentionally contains no authentication,
business-domain endpoints, or persistence models yet.

## Local commands

```bash
uv sync --frozen --all-packages --all-groups
cd apps/api
uv run uvicorn careeros_api.main:app --reload --port 8000
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

Migrations are owned by `packages/backend`. From the repository root, run
`uv run --package careeros-backend alembic -c packages/backend/alembic.ini upgrade head`.

Configuration uses `CAREEROS_`-prefixed environment variables. The default
database URL is suitable only for local development. Production configuration
rejects debug mode, wildcard trusted hosts, and the known development database
credential. Database URLs are represented as secrets and are never returned by
the metadata endpoint.

Alembic uses the same validated database setting as the API. The initial
migration enables the `vector` PostgreSQL extension and intentionally creates no
business tables. The downgrade does not remove the shared extension.

Operational endpoints:

- `GET /health` is a process liveness check and never calls dependencies.
- `GET /ready` checks the PostgreSQL connection and returns HTTP 503 when it is
  unavailable.
- `GET /api/v1/meta` returns non-sensitive service metadata and the required
  scoring disclaimer.
