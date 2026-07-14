# CareerOS API

Thin FastAPI delivery service for the shared CareerOS backend. Phase 1 composes
the identity, account, consent, session, Google OAuth, and onboarding application
services without moving domain or persistence ownership into the deployable.

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

Run the real PostgreSQL/Redis identity integrations and full browser workflow from
the repository root with `.\scripts\verify-phase1.ps1` on PowerShell or
`tests/e2e/run-compose.sh` in a POSIX environment.

Migrations are owned by `packages/backend`. From the repository root, run
`uv run --package careeros-backend alembic -c packages/backend/alembic.ini upgrade head`.

Configuration uses `CAREEROS_`-prefixed environment variables. The default
database URL is suitable only for local development. Production configuration
rejects debug mode, wildcard trusted hosts, and the known development database
credential. Database URLs are represented as secrets and are never returned by
the metadata endpoint.

Alembic uses the same validated database setting as the API. The initial migration
enables the `vector` PostgreSQL extension. Migration `20260715_0002` adds Phase 1
identity/session/account tables and can downgrade to the foundation revision
before a forward repair.

Operational endpoints:

- `GET /health` is a process liveness check and never calls dependencies.
- `GET /ready` checks required PostgreSQL, Redis, and SMTP dependencies and returns
  HTTP 503 with safe diagnostics when one is unavailable.
- `GET /api/v1/meta` returns non-sensitive service metadata and the required
  scoring disclaimer.

The authoritative implemented identity surface is the generated OpenAPI document.
It includes registration/verification, login/refresh/logout/recovery, session
management, Google OAuth, `/me`, onboarding, and consent operations. Browser
sessions use HTTP-only cookies plus session-bound CSRF and origin checks; token or
credential values must never be logged. See `docs/api.md` and ADR 0008.
