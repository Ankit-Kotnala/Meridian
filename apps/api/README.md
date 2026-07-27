# CareerOS API

Thin FastAPI delivery service for the shared CareerOS backend. It composes the
implemented identity, Resume Health, Career Record, Role Explorer, Job Match,
Change Studio, Resume Builder, Application Workspace, Interview Prep,
Networking, Career Growth, and Career Analytics application services without
moving domain or persistence ownership into the deployable. FastAPI schemas are
the OpenAPI source of truth; domain rules and repositories remain in
`packages/backend`.

## Local commands

Run these from the repository root:

```bash
pnpm dev:api       # dependency containers plus FastAPI hot reload
pnpm test:api      # focused API tests
make format-check
make lint
make typecheck
```

Feature delivery files live under
`src/careeros_api/modules/<bounded_context>/{routes,schemas,presenters,dependencies}.py`.
Only concrete cross-cutting HTTP composition, middleware, configuration, and
problem handling remain at the package root. See `docs/local-development.md` for
the full repository map and container workflows.

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
migration enables the `vector` PostgreSQL extension. The current reviewed head is
`20260726_0013`; it follows Phase 9 head `20260724_0010`, the resume-ready closure
at `20260726_0011`, and the two durable export closure migrations. Migration
lifecycle, rollback/forward-repair, and compatibility tests run through their
owning phase verifiers. All four Phase 9 route families declare the shared safe
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
