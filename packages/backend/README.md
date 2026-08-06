# Rezumi backend

Shared Python foundation and domain/application owner for the Rezumi modular
monolith. Implemented bounded contexts cover identity, Resume Health, Career
Record, Role Readiness, Job Match, Change Studio, Resume Builder, Application
Workspace, Interview Prep, Networking, Career Growth, and Career Analytics.
Provider and cross-context dependencies stay behind application ports while
framework delivery concerns remain outside this package.

The package must never import either deployable application. FastAPI composition
belongs to `apps/api`, and Celery process/task composition belongs to
`apps/worker`.

## Workspace commands

Run from the repository root after `uv sync --frozen --all-packages --all-groups`:

```bash
uv run --package rezumi-backend ruff format --check packages/backend
uv run --package rezumi-backend ruff check packages/backend
uv run --package rezumi-backend mypy packages/backend/src packages/backend/tests
uv run --package rezumi-backend pytest packages/backend/tests/architecture packages/backend/tests/unit
uv run --package rezumi-backend pytest packages/backend/tests/integration
uv run --package rezumi-backend alembic -c packages/backend/alembic.ini heads
```

Integration tests require their documented isolated PostgreSQL/Redis/object-store
environment. Use `scripts/verify-phase9.ps1` or the Phase 9 isolated stack runner
for the complete migration/repository/browser portfolio; do not treat an
environment-driven skip as a pass.

Database upgrades require `REZUMI_DATABASE_URL` (or the compatibility alias
`DATABASE_URL`) and run with:

```bash
uv run --package rezumi-backend alembic -c packages/backend/alembic.ini upgrade head
```

Phase 9 migration `20260724_0010` adds Interview Prep, Networking, Career Growth,
and Career Analytics persistence after Phase 8 head `20260724_0009`. The current
reviewed head is `20260726_0013` after the resume-ready and durable export
closure migrations. Phase 9 includes explicit ownership, composite parent constraints,
exact evidence revision/hash provenance, immutable review/score snapshots,
third-party contact-consent history, parent-and-child withdrawal tombstones,
bounded CRM collections, trace-bound local reminder state, and durable
analytics/reminder jobs. Growth evidence-link provenance is revalidated on every
insert or update, and target rows are locked against a concurrent delete until
link creation commits. Analytics supplemental freshness is a window-aware hash
of the exact bounded canonical-eligible achievement and Role Readiness point set.
Its internal source window permits only the two UTC guard days around the
public 3,650-day maximum. The
Phase 9 lifecycle gate bootstraps a fresh database, rolls back to
`20260724_0009`, repairs forward, and verifies the conditional repair of a
pre-release Phase 8 development schema without rewriting the shipped Phase 8
migration.

The backend imports neither deployable application. One product module consumes
another only through an explicit application interface; architecture tests
enforce that domain code does not depend on FastAPI, SQLAlchemy, Redis, object
storage, Celery, or provider SDKs.
