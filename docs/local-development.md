# Local development

Rezumi keeps runtime boundaries explicit while providing one cross-platform
command surface from the repository root. Use the root commands below instead of
manually reconstructing service dependencies or changing directories.

## Where to make a change

| Change                                          | Primary location                                                   | Focused check                               |
| ----------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------- |
| Page, route shell, or metadata                  | `frontend/web/src/app`                                             | `npm run test:web`                             |
| Product UI and state                            | `frontend/web/src/modules/<feature>`                               | `npm run test:web`                             |
| Reusable accessible UI                          | `frontend/ui/src`                                                  | `npm run test --workspace=@rezumi/ui`          |
| Visual tokens                                   | `frontend/design-tokens`                                           | `npm run build --workspace=@rezumi/design-tokens` |
| HTTP route, schema, presenter, or dependency    | `backend/api/src/rezumi_api/modules/<bounded_context>`             | `npm run test:api`                             |
| Cross-cutting HTTP composition or middleware    | `backend/api/src/rezumi_api`                                       | `npm run test:api`                             |
| Business rules and use cases                    | `backend/core/src/rezumi/modules/<bounded_context>`                | `npm run test:backend`                         |
| Database/provider adapter for a bounded context | `backend/core/src/rezumi/modules/<bounded_context>/infrastructure` | backend unit and integration tests          |
| Celery task adapter                             | `backend/worker/src/rezumi_worker/tasks/<bounded_context>.py`      | `npm run test:worker`                          |
| Worker runtime composition                      | `backend/worker/src/rezumi_worker/runtime.py`                      | `npm run test:worker`                          |
| OpenAPI wire contract                           | FastAPI schemas, then generated `shared/contracts` artifacts       | `npm run contracts:check`                      |
| Local/deployment infrastructure                 | `infra/compose.yaml` and `infra`                                   | `make compose-config`                       |
| Cross-service browser behavior                  | `frontend/web/e2e` and `tests/e2e`                                 | the applicable isolated E2E runner          |

Keep Next.js route files thin, keep API and Celery files as delivery adapters, and
put domain behavior in `backend/core`. Do not move persistence or queue access
into the web application.

## First setup

```powershell
.\scripts\setup.ps1
npm run local:up
npm run local:smoke
```

The same root `npm run` commands work in PowerShell, Command Prompt, Bash, and WSL.
GNU Make aliases are listed by `make help`.

`npm run local:up` builds and starts the complete stack detached. It leaves the
terminal free for tests and logs. Normal local commands preserve PostgreSQL,
Redis, MinIO, and ClamAV volumes.

## Choose the fastest workflow

| Goal                                      | Command                    | What runs                                               |
| ----------------------------------------- | -------------------------- | ------------------------------------------------------- |
| Run the complete product                  | `npm run local:up`            | Full Docker stack, detached and health-checked          |
| Work only on the UI                       | `npm run dev:web`             | Backend in Docker; Next.js on the host with hot reload  |
| Work on API delivery/backend use cases    | `npm run dev:api`             | Dependencies in Docker; FastAPI on the host with reload |
| Work on task adapters or worker runtime   | `npm run dev:worker`          | Dependencies in Docker; Celery worker on the host       |
| Run backend containers without the UI     | `npm run local:backend`       | API, worker, scheduler, and dependencies                |
| Start only stateful/security dependencies | `npm run local:deps`          | PostgreSQL, Redis, MinIO, Mailpit, and ClamAV           |
| Inspect state                             | `npm run local:status`        | `docker compose ps`                                     |
| Follow all logs                           | `npm run local:logs`          | Last 200 lines, then follow                             |
| Follow one service                        | `npm run local:logs -- api`   | One allowlisted Compose service                         |
| Probe a full stack                        | `npm run local:smoke`         | Web, API, and Mailpit HTTP probes                       |
| Probe backend-only mode                   | `npm run local:smoke:backend` | API and Mailpit HTTP probes                             |
| Stop safely                               | `npm run local:down`          | Stops containers; preserves volumes                     |

Hot-reload modes stop only the conflicting Compose service before starting the
host process. They do not delete containers or data. Host processes receive
loopback database, Redis, object-store, scanner, and mail endpoints derived from
`.env`, so developers do not have to rewrite Docker service hostnames manually.

For simultaneous host API and worker development, use two terminals:

```powershell
npm run dev:api
npm run dev:worker
```

## When Docker needs a rebuild

A host hot-reload process reflects source edits immediately. A container uses the
source captured when its image was built, so rebuild only the affected surface:

```powershell
npm run local:rebuild:web      # frontend/web, frontend/ui, design tokens, contracts
npm run local:rebuild:backend  # backend/api, backend/worker, backend/core
npm run local:rebuild          # both surfaces
```

You do not need `docker compose down` before a rebuild. Never use
`docker compose down -v` unless you explicitly intend to erase local data. The
existing destructive database reset remains `make reset-db` and is not exposed
through the normal local command script.

## Focused tests

Run the smallest relevant test while iterating:

```powershell
npm run test:web
npm run test:api
npm run test:worker
npm run test:backend
npm run contracts:check
```

Before opening a PR, run the repository gates required by `AGENTS.md`:

```powershell
make format-check
make lint
make typecheck
make test
```

Use `make test-integration` when API, worker, persistence, Compose, or contracts
change. Use the applicable isolated E2E runner when a browser workflow changes.
A skipped or unavailable required gate is a blocker, not a pass.

## API and worker layout

Feature-specific API files have one predictable address:

```text
backend/api/src/rezumi_api/modules/<bounded_context>/
  routes.py
  schemas.py
  presenters.py      # when response mapping is non-trivial
  dependencies.py    # when request composition is feature-specific
  problems.py        # when the feature owns safe problem translation
```

Only concrete cross-cutting HTTP concerns remain at `rezumi_api` root, such as
application composition, configuration, middleware, shared problem handling, and
the root router.

Celery task registration follows the same bounded contexts:

```text
backend/worker/src/rezumi_worker/tasks/
  career_analytics.py
  career_record.py
  networking.py
  resume_builder.py
  resume_health.py
  health.py
  contracts.py
  execution.py
```

Task names and broker payloads are stable; the package split is an ownership and
navigation boundary, not a new queue topology.

## Troubleshooting

- Run `npm run local:status` first. A container that is still starting is different
  from an unhealthy dependency.
- Run `npm run local:logs -- <service>` for one service without losing other state.
- If port 3000 or 8000 is occupied by Compose, use `npm run dev:web` or
  `npm run dev:api`; each stops its conflicting container safely.
- If generated contracts drift after an API schema change, run
  `npm run contracts:generate`, review both generated artifacts, and rerun
  `npm run contracts:check`.
- If a migration changes, verify one Alembic head and run the migration integration
  gate before browser tests.
