# Local development

Rezumi keeps runtime boundaries explicit while providing one cross-platform
command surface from the repository root. Use the root commands below instead of
manually reconstructing service dependencies or changing directories.

## Where to make a change

| Change                                          | Primary location                                                       | Focused check                               |
| ----------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------- |
| Page, route shell, or metadata                  | `apps/web/src/app`                                                     | `pnpm test:web`                             |
| Product UI and state                            | `apps/web/src/modules/<feature>`                                       | `pnpm test:web`                             |
| Reusable accessible UI                          | `packages/ui/src`                                                      | `pnpm --filter @rezumi/ui test`             |
| Visual tokens                                   | `packages/design-tokens`                                               | `pnpm --filter @rezumi/design-tokens build` |
| HTTP route, schema, presenter, or dependency    | `apps/api/src/rezumi_api/modules/<bounded_context>`                    | `pnpm test:api`                             |
| Cross-cutting HTTP composition or middleware    | `apps/api/src/rezumi_api`                                              | `pnpm test:api`                             |
| Business rules and use cases                    | `packages/backend/src/rezumi/modules/<bounded_context>`                | `pnpm test:backend`                         |
| Database/provider adapter for a bounded context | `packages/backend/src/rezumi/modules/<bounded_context>/infrastructure` | backend unit and integration tests          |
| Celery task adapter                             | `apps/worker/src/rezumi_worker/tasks/<bounded_context>.py`             | `pnpm test:worker`                          |
| Worker runtime composition                      | `apps/worker/src/rezumi_worker/runtime.py`                             | `pnpm test:worker`                          |
| OpenAPI wire contract                           | FastAPI schemas, then generated `packages/contracts` artifacts         | `pnpm contracts:check`                      |
| Local/deployment infrastructure                 | `compose.yaml` and `infra`                                             | `docker compose config --quiet`             |
| Cross-service browser behavior                  | `apps/web/e2e` and `tests/e2e`                                         | the applicable isolated E2E runner          |

Keep Next.js route files thin, keep API and Celery files as delivery adapters, and
put domain behavior in `packages/backend`. Do not move persistence or queue access
into the web application.

## First setup

```powershell
.\scripts\setup.ps1
pnpm local:up
pnpm local:smoke
```

The same root `pnpm` commands work in PowerShell, Command Prompt, Bash, and WSL.
GNU Make aliases are listed by `make help`.

`pnpm local:up` builds and starts the complete stack detached. It leaves the
terminal free for tests and logs. Normal local commands preserve PostgreSQL,
Redis, MinIO, and ClamAV volumes.

## Choose the fastest workflow

| Goal                                      | Command                    | What runs                                               |
| ----------------------------------------- | -------------------------- | ------------------------------------------------------- |
| Run the complete product                  | `pnpm local:up`            | Full Docker stack, detached and health-checked          |
| Work only on the UI                       | `pnpm dev:web`             | Backend in Docker; Next.js on the host with hot reload  |
| Work on API delivery/backend use cases    | `pnpm dev:api`             | Dependencies in Docker; FastAPI on the host with reload |
| Work on task adapters or worker runtime   | `pnpm dev:worker`          | Dependencies in Docker; Celery worker on the host       |
| Run backend containers without the UI     | `pnpm local:backend`       | API, worker, scheduler, and dependencies                |
| Start only stateful/security dependencies | `pnpm local:deps`          | PostgreSQL, Redis, MinIO, Mailpit, and ClamAV           |
| Inspect state                             | `pnpm local:status`        | `docker compose ps`                                     |
| Follow all logs                           | `pnpm local:logs`          | Last 200 lines, then follow                             |
| Follow one service                        | `pnpm local:logs -- api`   | One allowlisted Compose service                         |
| Probe a full stack                        | `pnpm local:smoke`         | Web, API, and Mailpit HTTP probes                       |
| Probe backend-only mode                   | `pnpm local:smoke:backend` | API and Mailpit HTTP probes                             |
| Stop safely                               | `pnpm local:down`          | Stops containers; preserves volumes                     |

Hot-reload modes stop only the conflicting Compose service before starting the
host process. They do not delete containers or data. Host processes receive
loopback database, Redis, object-store, scanner, and mail endpoints derived from
`.env`, so developers do not have to rewrite Docker service hostnames manually.

For simultaneous host API and worker development, use two terminals:

```powershell
pnpm dev:api
pnpm dev:worker
```

## When Docker needs a rebuild

A host hot-reload process reflects source edits immediately. A container uses the
source captured when its image was built, so rebuild only the affected surface:

```powershell
pnpm local:rebuild:web      # apps/web, packages/ui, design tokens, contracts
pnpm local:rebuild:backend  # apps/api, apps/worker, packages/backend
pnpm local:rebuild          # both surfaces
```

You do not need `docker compose down` before a rebuild. Never use
`docker compose down -v` unless you explicitly intend to erase local data. The
existing destructive database reset remains `make reset-db` and is not exposed
through the normal local command script.

## Focused tests

Run the smallest relevant test while iterating:

```powershell
pnpm test:web
pnpm test:api
pnpm test:worker
pnpm test:backend
pnpm contracts:check
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
apps/api/src/rezumi_api/modules/<bounded_context>/
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
apps/worker/src/rezumi_worker/tasks/
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

- Run `pnpm local:status` first. A container that is still starting is different
  from an unhealthy dependency.
- Run `pnpm local:logs -- <service>` for one service without losing other state.
- If port 3000 or 8000 is occupied by Compose, use `pnpm dev:web` or
  `pnpm dev:api`; each stops its conflicting container safely.
- If generated contracts drift after an API schema change, run
  `pnpm contracts:generate`, review both generated artifacts, and rerun
  `pnpm contracts:check`.
- If a migration changes, verify one Alembic head and run the migration integration
  gate before browser tests.
