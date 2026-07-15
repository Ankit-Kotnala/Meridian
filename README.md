# CareerOS

**Your career. Verified. Elevated.**

CareerOS is a career application operating system. It turns a structured,
evidence-backed career profile into resume analyses, tailored documents,
application materials, and interview preparation while keeping every factual
claim under the user's control.

> CareerOS scores are internal readiness measurements. They are not scores
> provided by an employer or applicant tracking system and do not guarantee
> interviews or employment outcomes.

## Repository status

**Phase 1 authentication, onboarding, and the protected workspace are complete;
Phase 2 resume upload, parsing, and general health is next.** The repository uses a
shared Python modular monolith, one root uv workspace, generated API contracts,
thin deployable applications, and executable dependency boundaries.

Hosted CI run `29366505373` passed GitGuardian plus all seven repository jobs
against Phase 1 commit `c4bdbe1`, including API, worker, web/contracts, browser,
auth E2E, supply-chain, and clean-checkout container/migration/image scanning.

See [PLANS.md](PLANS.md) for current status, historical evidence, and phase gates.
Do not infer that a planned endpoint or module is implemented from the
architecture documents.

## Stack

- Web: Node.js 24, pnpm 11.13.0, Next.js 16.2.10 App Router, React 19.2.7,
  TypeScript 5.9.3 strict mode, and Tailwind CSS 4.3.2
- API: Python 3.13, uv, FastAPI 0.138.2, Pydantic, async SQLAlchemy, and asyncpg
- Worker: Celery 5.6.3 with Redis broker/result backend
- Local services: PostgreSQL with pgvector, Redis, S3-compatible MinIO, and
  Mailpit SMTP capture
- Backend: shared `careeros-backend` modular monolith used by thin API and worker
  deployables through one root uv workspace and lockfile
- Contracts: FastAPI OpenAPI as the source of truth, with a normalized artifact,
  generated TypeScript schema, and typed client wrapper in `packages/contracts`

## Repository map

```text
apps/
  web/                 Next.js application
  api/                 Thin FastAPI delivery application
  worker/              Thin Celery delivery application
packages/
  backend/             Shared Python foundation and phase-owned modules
  contracts/           OpenAPI artifact, generated schema, typed client wrapper
  ui/                  Generic accessible React components
  design-tokens/       Shared visual tokens
  eslint-config/       Frontend lint and dependency-boundary rules
  typescript-config/   Shared strict TypeScript configuration
  test-fixtures/       Explicitly fictional fixtures
docs/                  Product, architecture, security, API, and ADRs
infra/                 Implemented local container infrastructure
scripts/               Repository automation
```

## Prerequisites

The supported local stack is containerized, while dependency installation and
quality checks run through the pinned host toolchains. Install:

- Docker Engine/Desktop with Compose v2
- Node.js 24 with Corepack
- Python 3.13 and uv (CI pins uv 0.11.21)
- Git
- either GNU Make plus a POSIX shell (WSL/Git Bash are suitable on Windows), or
  PowerShell and the checked-in scripts

Docker must have enough memory for the web, API, worker, PostgreSQL, Redis, MinIO,
and Mailpit services.

## First-time setup

From the repository root with GNU Make:

```sh
cp .env.example .env
make setup
make dev
```

Native PowerShell setup and start:

```powershell
.\scripts\setup.ps1
docker compose up --build
```

`make setup` installs or prepares pinned dependencies and initializes the local
environment. `make dev` starts the Compose stack. It stays attached unless the
Make target documents otherwise; `docker compose up --build` has the same attached
runtime behavior on the PowerShell path. Use a second terminal for probes and
checks. Both setup paths create `.env` from `.env.example` when it is absent.
Local values in `.env.example` are development-only and must never be reused in a
shared or production environment.

Expected local entry points:

Compose binds every published port to `127.0.0.1`; the disposable local
credentials are not exposed on other host interfaces by default.

| Service       | URL                                 | Purpose                     |
| ------------- | ----------------------------------- | --------------------------- |
| Web           | <http://localhost:3000>             | Public and authenticated UI |
| Web health    | <http://localhost:3000/api/health>  | Web liveness                |
| API docs      | <http://localhost:8000/docs>        | OpenAPI UI                  |
| API liveness  | <http://localhost:8000/health>      | Process health              |
| API readiness | <http://localhost:8000/ready>       | Dependency health           |
| API metadata  | <http://localhost:8000/api/v1/meta> | Safe service metadata       |
| MinIO API     | <http://localhost:9000>             | S3-compatible endpoint      |
| MinIO console | <http://localhost:9001>             | Local object administration |
| Mailpit       | <http://localhost:8025>             | Local auth email capture    |

Create an account at `/register`, follow the verification link captured by
Mailpit, and sign in at `/login`. Other public flow routes are `/verify-email`,
`/forgot-password`, `/reset-password`, and `/get-started`. `/dashboard`,
`/onboarding`, `/settings`, `/settings/sessions`, and `/settings/consent` require an
authenticated session. The labeled fictional preview remains available at
`/demo/dashboard`; it is isolated from real account state.

Check the composed service state and probes:

```sh
docker compose ps
curl --fail http://localhost:3000/api/health
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ready
curl --fail http://localhost:8000/api/v1/meta
```

PowerShell can use `Invoke-WebRequest -UseBasicParsing` in place of `curl` if
`curl.exe` is unavailable.

Stop services without deleting volumes:

```sh
make stop
```

PowerShell equivalent:

```powershell
docker compose down --remove-orphans
```

`make reset-db` is destructive to local development data. Inspect the target and
make a backup before running it; never use it against shared or production data.

## Development commands

Run `make help` for the authoritative target list. The intended stable interface
is:

```sh
make setup            # prepare pinned dependencies and local configuration
make dev              # start the local platform
make stop             # stop local services, preserving volumes
make format           # apply supported formatters
make format-check     # verify formatting without writing
make lint             # lint TypeScript and Python
make typecheck        # strict TypeScript and Python type checks
make test             # unit tests
make test-integration # build/start the stack, migrate twice, and probe services
make test-e2e         # Playwright against an already running stack
make test-e2e-stack   # isolated desktop/mobile authentication journey
make security-scan    # scan source, dependencies, and application images
make migrate          # apply the current database migrations
make seed             # print the explicitly fictional Phase 0 fixture
make verify           # full format/lint/type/test/contract/build/runtime gate
make verify-phase1    # full gate plus isolated Phase 1 integration/E2E
make reset-db         # explicitly destructive local database reset
```

On native Windows without GNU Make, use `.\scripts\setup.ps1` for `make setup`,
`.\scripts\verify.ps1` for the full contract/quality/build/migration/runtime
gate, `.\scripts\security-scan.ps1` for `make security-scan`, and the equivalent
`docker compose` commands shown above for start/stop. Use
`.\scripts\verify-phase1.ps1` for the consolidated Phase 1 gate, including isolated
PostgreSQL/Redis integration and Playwright journeys. The general verification
script leaves the healthy local stack running for inspection. The Phase 1 E2E
runner cleans up its isolated containers, images, networks, and volumes.

The Phase 0 migration enables the pgvector extension. Phase 1 migration
`20260715_0002` adds the identity, session, OAuth, organization, consent, audit,
and onboarding tables with ownership and integrity constraints. The seed command
still prints only a fictional demo fixture and performs no database write. A
command that prints a fixture or says a feature is deferred is not evidence that
the product feature exists.

For host-only package work, use the pinned tools rather than global substitutes:

```sh
corepack enable
pnpm install --frozen-lockfile
uv sync --frozen --all-packages --all-groups
```

The root uv workspace contains `apps/api`, `apps/worker`, and
`packages/backend`. Do not create per-application locks or make the worker import
the API.

## Product and engineering guardrails

- A career profile and its evidence—not an imported resume—are the durable source
  of truth.
- CareerOS never fabricates career facts. Missing evidence generates a question.
- Material edits require review, evidence visibility, and explicit user action.
- Scores are deterministic, versioned, explainable internal measurements; an LLM
  never supplies the final numeric score.
- All user data is ownership-scoped and authorization is enforced server-side.
- Raw resumes and job descriptions are not logged or placed in analytics.
- Uploaded documents, imported URLs, and model output are untrusted input.
- Public demo content is fictional and visibly labeled.

Read [AGENTS.md](AGENTS.md) before contributing. The principal references are:

- [Documentation index](docs/README.md)
- [Architecture](docs/architecture.md)
- [Product requirements](docs/product-requirements.md)
- [Security threat model](docs/security-threat-model.md)
- [Scoring methodology](docs/scoring-methodology.md)
- [AI grounding policy](docs/ai-grounding-policy.md)
- [API conventions](docs/api.md)
- [Implementation checklist](docs/implementation-checklist.md)
- [Architecture decisions](docs/adr/README.md)

## Phase 0 and Phase 1 verification

The aligned working tree passes the repository gates, architecture checks,
contract drift checks, migrations, browser checks, security scans, and container
paths represented by the commands below. Exact current and historical results are
recorded separately in `PLANS.md`:

```sh
make setup
make dev
docker compose ps
make format-check
make lint
make typecheck
make test
make verify
make test-e2e
```

Native PowerShell runs the equivalent quality/build/configuration checks with:

```powershell
.\scripts\setup.ps1
.\scripts\verify.ps1
.\scripts\verify-phase1.ps1
docker compose up --build --detach --wait
docker compose ps
Invoke-WebRequest -UseBasicParsing http://localhost:3000/api/health
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health
Invoke-WebRequest -UseBasicParsing http://localhost:8000/ready
Invoke-WebRequest -UseBasicParsing http://localhost:8000/api/v1/meta
```

The Phase 1 gate passes formatting, lint, strict types, contract drift, unit and
API tests, production builds, migration round-trip, all local service readiness,
two real PostgreSQL/Redis identity integrations, and the primary desktop/mobile
auth workflow. Playwright reports 9 passed, 1 intentional desktop-only project
exclusion, and 0 failures. Hosted CI run `29366505373` verifies the Phase 1 commit;
the earlier Phase 0 evidence remains in `PLANS.md`. Skipped, unavailable, or
failing required checks reopen the phase.

## License and production use

No license or production deployment approval has been selected in Phase 0.
Treat the repository as private and non-production until those decisions, a
security review, data-processing terms, retention defaults, backup/restore tests,
and a protected deployment environment are complete.
