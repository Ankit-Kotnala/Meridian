# CareerOS backend

Shared Python foundation and domain/application owner for the CareerOS modular
monolith. Phase 1 adds `careeros.modules.identity` plus email and Google OAuth
integration ports/adapters while keeping framework delivery concerns outside this
package.

The package must never import either deployable application. FastAPI composition
belongs to `apps/api`, and Celery process/task composition belongs to
`apps/worker`.

## Workspace commands

Run from the repository root after `uv sync --frozen --all-packages --all-groups`:

```bash
uv run --package careeros-backend ruff format --check packages/backend
uv run --package careeros-backend ruff check packages/backend
uv run --package careeros-backend mypy packages/backend/src packages/backend/tests
uv run --package careeros-backend pytest packages/backend/tests/architecture packages/backend/tests/unit
uv run --package careeros-backend alembic -c packages/backend/alembic.ini heads
```

Database upgrades require `CAREEROS_DATABASE_URL` (or the compatibility alias
`DATABASE_URL`) and run with:

```bash
uv run --package careeros-backend alembic -c packages/backend/alembic.ini upgrade head
```

The current head, `20260715_0002`, owns the Phase 1 user/profile, session/token,
OAuth, organization/membership, consent, audit, and onboarding tables. Identity
tests include fast in-memory domain/application coverage and explicitly selected
real PostgreSQL/Redis integrations. Run the latter through `make test-e2e-stack`
or `scripts/test-e2e-stack.ps1`; they are not silently skipped in the unit gate.
