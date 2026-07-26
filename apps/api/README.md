# CareerOS API

Thin FastAPI delivery service for the shared CareerOS backend. It composes the
implemented identity, Resume Health, Career Record, Role Explorer, Job Match,
Change Studio, Resume Builder, Application Workspace, Interview Prep,
Networking, Career Growth, and Career Analytics application services without
moving domain or persistence ownership into the deployable. FastAPI schemas are
the OpenAPI source of truth; domain rules and repositories remain in
`packages/backend`.

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

Run the complete current integration and browser portfolio from the repository
root with `.\scripts\verify-phase9.ps1` on PowerShell or
`CAREEROS_E2E_PHASE=9 tests/e2e/run-compose.sh` in a POSIX environment. Focused
API tests remain credential-free through deterministic/local adapters.

Migrations are owned by `packages/backend`. From the repository root, run
`uv run --package careeros-backend alembic -c packages/backend/alembic.ini upgrade head`.

Configuration uses `CAREEROS_`-prefixed environment variables. The default
database URL is suitable only for local development. Production configuration
rejects debug mode, wildcard trusted hosts, and the known development database
credential. Database URLs are represented as secrets and are never returned by
the metadata endpoint.

Alembic uses the same validated database setting as the API. The initial
migration enables the `vector` PostgreSQL extension. The current Phase 9 head is
`20260724_0010`; it adds the Interview Prep, Networking, Career Growth, and
Career Analytics tables after Phase 8 head `20260724_0009`. Migration lifecycle,
rollback/forward-repair, and pre-release Phase 8 compatibility tests run through
the Phase 9 verifier. All four Phase 9 route families declare the shared safe
`413` streamed-body response and a typed `429` collection-quota response. Their
domain handlers keep quota exhaustion distinct from validation, version, and
idempotency conflicts.

Operational endpoints:

- `GET /health` is a process liveness check and never calls dependencies.
- `GET /ready` checks required PostgreSQL, Redis, and SMTP dependencies and returns
  HTTP 503 with safe diagnostics when one is unavailable.
- `GET /api/v1/meta` returns non-sensitive service metadata and the required
  scoring disclaimer.

The implemented FastAPI schemas are authoritative. The normalized OpenAPI
document under `packages/contracts/openapi` and the generated TypeScript schema
are committed review artifacts and must not be hand-edited. Browser sessions use
HTTP-only cookies plus session-bound CSRF and origin checks. Owner-scoped private
reads are `no-store`; mutations use CSRF, idempotency keys, and quoted versions
where defined. Token, credential, resume, evidence, contact, note, and
generated-content values must never enter request logs. See `docs/api.md` and the
ADR index.
