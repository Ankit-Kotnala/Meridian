# ADR 0007: Shared modular-monolith backend and generated contracts

- Status: Accepted
- Date: 2026-07-14
- Deciders: Engineering
- Supersedes in part: [ADR 0001](0001-monorepo-and-runtime-topology.md)

## Context

ADR 0001 established independently deployable API and worker applications with
separate Python project lockfiles. The Phase 0 architecture addendum subsequently
requires both applications to be thin delivery processes over one shared Python
modular monolith, one uv workspace lock, executable dependency boundaries, and
frontend contracts generated from FastAPI OpenAPI.

Keeping database, migrations, logging, and later application use cases inside a
deployable would make the other process depend on application internals or
duplicate business rules. Handwritten TypeScript wire models would create a
second contract authority and allow silent drift.

## Decision

Use one root uv workspace containing:

- `backend/api`, the thin FastAPI HTTP delivery and composition application;
- `backend/worker`, the thin Celery delivery and process application; and
- `backend/core`, the shared Python modular-monolith implementation.

The workspace has one committed root `uv.lock`. Both deployables depend on
`rezumi-backend`; the backend imports neither deployable, and the worker never
imports the API.

In Phase 0, `backend/core/src/rezumi/foundation` owns only stable shared
database, migration, configuration, and structured-logging primitives. Alembic
configuration and revision history live with this package. Product modules use
`domain`, `application`, `infrastructure`, `api`, `tasks`, and tests when their
owning phase begins. Provider SDK adapters live under `rezumi.integrations`.
Empty future module and integration trees are prohibited.

FastAPI OpenAPI is the only wire-contract authority. A normalized OpenAPI artifact
is committed under `shared/contracts/openapi`, and pinned generation produces
the TypeScript schema consumed by the package's typed `openapi-fetch` wrapper.
Generated artifacts are never manually patched. CI must fail when exporting or
regenerating changes the committed artifacts.

Static architecture tests enforce forbidden backend imports and deployable
dependency direction. Frontend lint or dependency checks keep route files thin,
feature behavior under `frontend/web/src/modules`, and generic UI in `frontend/ui`.

## Consequences

### Positive

- API and worker reuse one set of business rules and persistence abstractions
  while remaining separately deployable.
- One Python resolution prevents app lockfiles from drifting.
- Migrations have one owner and revision graph.
- Frontend consumers compile against the implemented API rather than parallel
  handwritten models.
- Dependency rules are executable and can block accidental coupling early.

### Costs and risks

- Python image builds require the repository root context and a strict
  `.dockerignore`.
- Moving Alembic must preserve revision identifiers and work against fresh and
  existing databases.
- A shared package can become a dumping ground; foundation content must be stable,
  domain-independent, and genuinely shared.
- Generated artifacts add review noise unless export and generation are pinned
  and deterministic.
- The workspace, containers, migrations, contracts, and all prior Phase 0 gates
  must be reverified together before Phase 0 can close again.

## Alternatives considered

- **Keep independent Python projects and duplicate shared behavior:** preserves
  small build contexts but creates drift and violates the required dependency
  direction.
- **Let the worker import API services:** avoids a package initially but couples a
  background deployable to HTTP composition and can trigger API startup behavior.
- **Publish the backend as a separate repository/package:** adds release and
  version coordination without a current team or deployment boundary that
  justifies it.
- **Maintain handwritten TypeScript schemas:** offers runtime validation but
  creates a competing contract authority. Runtime validation may be generated or
  added at trust boundaries without duplicating the public wire model.

## Verification

Phase 0 remains open until one revision proves:

- a frozen root uv install and a single root lockfile;
- architecture tests for backend, API, and worker dependency direction;
- a single Alembic head plus fresh and existing-database upgrades;
- deterministic OpenAPI export and generated-schema drift checks;
- API and worker container builds from the root context;
- the documented format, lint, type, unit, integration, browser, security, and
  Compose health gates.

Prior Phase 0 evidence predates this decision and remains historical evidence,
not verification of the aligned architecture.
