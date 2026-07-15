# CareerOS backend

Shared Python foundation for the CareerOS modular monolith. In Phase 0 this
package owns only reusable database, migration, and observability primitives.
Product modules and provider integrations are added only when their phase begins.

The package must never import either deployable application. FastAPI composition
belongs to `apps/api`, and Celery process/task composition belongs to
`apps/worker`.

## Workspace commands

Run from the repository root after `uv sync --frozen --all-packages --all-groups`:

```bash
cd packages/backend
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run alembic heads
```

Database upgrades require `CAREEROS_DATABASE_URL` (or the compatibility alias
`DATABASE_URL`) and run with:

```bash
uv run alembic upgrade head
```
