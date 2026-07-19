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

**Phase 7 Resume Builder and verified export is implemented and locally verified in this working tree.**
Phases 0 through 3 are hosted verified; Phase 4 has local closeout evidence; and
Phases 5 through 7 final local gate evidence is recorded in `PLANS.md`. The
repository uses a shared Python modular monolith, one root uv workspace,
generated API contracts, thin deployable applications, and executable dependency
boundaries.

Hosted CI run `29657932938` passed every Phase 3 job on no-change trigger commit
`f752b55`, whose tree is identical to implementation commit `0df8bcf`; prior
Phase 2 evidence remains preserved at `3b8d639` and run `29378312134`.

See [PLANS.md](PLANS.md) for current status, historical evidence, and phase gates.
Do not infer that a planned endpoint or module is implemented from the
architecture documents.

## Stack

- Web: Node.js 24, pnpm 11.13.0, Next.js 16.2.10 App Router, React 19.2.7,
  TypeScript 5.9.3 strict mode, and Tailwind CSS 4.3.2
- API: Python 3.13, uv, FastAPI 0.138.2, Pydantic, async SQLAlchemy, and asyncpg
- Worker: Celery 5.6.3 with Redis broker/result backend
- Local services: PostgreSQL with pgvector, Redis, private S3-compatible MinIO,
  required ClamAV scanning, and Mailpit SMTP capture
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

Docker must have enough memory for the web, API, worker/scheduler, PostgreSQL,
Redis, MinIO, ClamAV, and Mailpit services. The local ClamAV container alone is
configured for up to 2 GiB.

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
`/onboarding`, `/settings`, `/settings/sessions`, `/settings/consent`,
`/career-profile`, `/evidence`, and `/achievement-inbox` require an authenticated
session. The labeled fictional preview remains available at
`/demo/dashboard`; it is isolated from real account state.

Career Profile is independent of resume upload. It stores user-owned experience,
typed career items, and skills with year/month precision, explicit grouping,
optimistic concurrency, source provenance, and reviewable import proposals.
Evidence Vault keeps evidence strength separate from lifecycle and downstream
eligibility. Owner confirmation can produce `Confirmed`; no independent verifier
is configured, so the production API cannot produce `Verified`. Achievement
Inbox preserves drafts and converts them to confirmed evidence only after an
explicit user action. Private evidence attachments use the same fail-closed
PDF/DOCX scanner and bounded extractor contracts without reusing Resume Health
persistence.

Role Explorer is available at `/role-explorer`. It uses the versioned Phase 4
seed taxonomy, saved roles, deterministic evidence-linked readiness analysis,
history, and two-or-three-role comparison. Results consume only the owner-scoped
Career Record readiness snapshot and display the canonical internal-score
disclaimer.

Job Match is available at `/job-match`. It saves pasted or safely imported job
postings, extracts source-spanned requirements, compares each requirement against
eligible Career Record evidence, shows mandatory gaps, and calculates an
explainable opportunity priority. It does not display raw saved job text in API
responses and does not describe scores as employer, ATS, or hiring-probability
scores.

Change Studio is available at `/change-studio` and from a completed Job Match
analysis. It uses eligible Career Record evidence plus saved job requirements to
generate structured suggestions, shows original/proposed text, reason, evidence,
requirement, grounding status, risk, and clarifying questions, and requires
explicit accept/reject/edit actions before the current version changes. The
local deterministic provider only reuses eligible evidence text; remote provider
configuration is HTTPS/API-key gated and still passes strict grounding before
display.

Resume Builder is available at `/resume-builder`. It creates structured,
evidence-backed resume drafts from the owner-scoped Career Record and optional
Change Studio output, preserves immutable versions, offers five constrained
ATS-friendly templates, renders PDF/DOCX/text/JSON exports, re-parses generated
files before download, shows the verification report, blocks critical failures,
and issues only short-lived owner-checked download intents. Exported files remain
pinned to the version and content hash that passed verification.

Authenticated Resume Health starts at `/resume-health/account`. The intentionally
limited guest flow starts at `/resume-health/guest`, uses one opaque short-lived
browser capability, permits one active intake, and defaults to 24-hour retention.
Both paths use real PDF/DOCX direct upload, required scanning, processing status,
source-preserving canonical review/correction, and deterministic analysis. An
image-only or sparse document returns insufficient data rather than a zero score.
The report exposes the persisted feature schema, measured values, and weighted
component contribution trace through keyboard-operable disclosures. Guest data
moves into an account only through the explicit consented claim path.

The mounted upload flow can retry an ambiguous transfer/finalize with the same
short-lived intent and idempotency key. That retry state is intentionally not
persisted in browser storage: after a lost intent response or page reload, quota
may remain reserved until the default five-minute intent TTL expires. Phase 2
does not implement resumable/chunked file transfer.

The local extractor enforces an authoritative page cap for PDF only.
`python-docx` has no reliable rendered page count, so DOCX is bounded by byte,
archive/expansion, extracted-character/block, artifact, and worker-resource
limits until a layout-aware rendering provider is introduced.

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
make test-e2e-stack   # isolated desktop/mobile auth and Resume Health journeys
make test-e2e-stack-phase3 # isolated Phase 3 desktop primary journey plus prior regressions
make test-e2e-stack-phase4 # isolated Phase 4 Role Explorer journey plus prior regressions
make test-e2e-stack-phase5 # isolated Phase 5 Job Match journey plus prior regressions
make test-e2e-stack-phase6 # isolated Phase 6 Change Studio journey plus prior regressions
make test-e2e-stack-phase7 # isolated Phase 7 Resume Builder journey plus prior regressions
make security-scan    # scan source, dependencies, app images, and trusted edge runtime
make migrate          # apply the current database migrations
make seed             # print the explicitly fictional Phase 0 fixture
make verify           # full format/lint/type/test/contract/build/runtime gate
make verify-phase1    # full gate plus isolated Phase 1 integration/E2E
make verify-phase2    # full gate plus isolated Resume Health integration/E2E
make verify-phase3    # full gate plus isolated Career Record integration/E2E
make verify-phase4    # full gate plus isolated Role Explorer integration/E2E
make verify-phase5    # full gate plus isolated Job Match integration/E2E
make verify-phase6    # full gate plus isolated Change Studio integration/E2E
make verify-phase7    # full gate plus isolated Resume Builder integration/E2E
make reset-db         # explicitly destructive local database reset
```

On native Windows without GNU Make, use `.\scripts\setup.ps1` for `make setup`,
`.\scripts\verify.ps1` for the full contract/quality/build/migration/runtime
gate, `.\scripts\security-scan.ps1` for `make security-scan`, and the equivalent
`docker compose` commands shown above for start/stop. Use
`.\scripts\verify-phase1.ps1` for the consolidated Phase 1 gate, including isolated
PostgreSQL/Redis integration and Playwright journeys. The general verification
script leaves the healthy local stack running for inspection. The Phase 1 E2E
baseline used the isolated runner, which cleans up its containers, images,
networks, and volumes.
Use `.\scripts\verify-phase2.ps1` for the Phase 2 migration, real
PostgreSQL/Redis/MinIO/ClamAV contracts, restricted worker, and registered/guest
Playwright workflows. It also cleans its isolated containers, images, networks,
volumes, and browser artifacts. A successful narrow test is not a substitute for
this complete closeout gate. Use `.\scripts\verify-phase3.ps1` for migration
`20260715_0004`, Career Record repository and attachment-provider integration,
the durable attachment worker, and the desktop Career Profile/Evidence/
Achievement primary journey. Shared workspace responsive behavior continues to
run in the existing mobile suites; the Phase 3 primary journey itself is
intentionally desktop-only. Run `make security-scan` (or its PowerShell
equivalent) separately; the phase verification scripts do not replace the
source, dependency, application-image, and pinned `web-edge` runtime scans.
Use `.\scripts\verify-phase5.ps1` for migration `20260719_0006`, Job Match
repository integration, and the desktop save/analyze/prioritize workflow backed
by confirmed career evidence. Shared responsive shell behavior remains covered
by the inherited desktop/mobile suites. Use `.\scripts\verify-phase6.ps1` for
migration `20260719_0007`, Change Studio repository integration, grounding/
provider tests, and the desktop generate/review/accept/undo/answer workflow
backed by confirmed career evidence and saved job requirements.
Use `.\scripts\verify-phase7.ps1` for migration `20260719_0008`, Resume Builder
repository integration, renderer/round-trip verification tests, and the desktop
create/version/export/download-intent workflow backed by confirmed career
evidence.

The Phase 0 migration enables the pgvector extension. Phase 1 migration
`20260715_0002` adds the identity, session, OAuth, organization, consent, audit,
and onboarding tables with ownership and integrity constraints. Phase 2 migration
`20260715_0003` adds guest capabilities, upload/document/artifact state, durable
jobs/outbox and object cleanup, fenced execution leases, immutable canonical
snapshots, Resume Health analyses with feature schema/values/component
contributions/findings, and redacted resume audit events with exactly-one-owner
constraints.
Phase 3 migration `20260715_0004` adds owner-scoped career profiles, typed career
entities and skills, import proposals, immutable evidence revisions/sources/
metrics/links/conflicts/usage, private attachment admission/jobs/outbox/cleanup,
achievement drafts, reminder preferences, and redacted Career Record audit
events. It is additive to the Phase 2 head; downgrading it deletes Phase 3 data
and therefore is a test/forward-repair mechanism, not an automatic production
rollback after real use.
Phase 4 migration `20260719_0005` adds the public versioned role taxonomy,
competencies, saved roles, readiness analyses/components/results/evidence links,
idempotency records, and redacted audit events. Downgrading to `20260715_0004`
deletes Phase 4 role-readiness data and is likewise a test/forward-repair path.
Phase 5 migration `20260719_0006` adds owner-scoped job postings, current
requirements, match analyses/components/requirement rows/evidence links,
opportunity priorities, idempotency records, and redacted audit events.
Downgrading to `20260719_0005` deletes Phase 5 job-match data and is likewise a
test/forward-repair path.
Phase 6 migration `20260719_0007` adds owner-scoped change sets, operations,
claim-ledger rows, clarifying questions, immutable output versions, provider-run
metadata, idempotency records, and redacted audit events. Downgrading to
`20260719_0006` deletes Phase 6 Change Studio data and is likewise a
test/forward-repair path.
Phase 7 migration `20260719_0008` adds owner-scoped structured resumes,
immutable resume versions, export records, verification reports, short-lived
download intents, idempotency records, and redacted audit events. Downgrading to
`20260719_0007` deletes Phase 7 resume-builder/export data and is likewise a
test/forward-repair path.
The seed command still prints only a fictional demo fixture and performs no
database write. A command that prints a fixture or says a feature is deferred is
not evidence that the product feature exists.

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

Local Compose publishes `web-edge`, not the Next.js container. The edge replaces
all client-selected forwarding headers with its socket peer before the otherwise
unexposed web BFF signs an opaque source key for pre-authentication and guest-
intake API abuse controls. This is a
local single-hop contract; a cloud load balancer requires an explicit allowlisted
trusted-hop design rather than accepting arbitrary forwarded addresses.

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

## Verification Status Through Phase 7 Implementation

Phases 0 through 3 have recorded local and hosted evidence; Phase 4 has recorded
local closeout evidence; Phases 5 through 7 have recorded local closeout evidence in
`PLANS.md`.
Exact current and historical results are recorded separately in `PLANS.md`; never
infer a pass from the command list below:

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
.\scripts\verify-phase2.ps1
.\scripts\verify-phase3.ps1
.\scripts\verify-phase4.ps1
.\scripts\verify-phase5.ps1
.\scripts\verify-phase6.ps1
.\scripts\verify-phase7.ps1
docker compose up --build --detach --wait
docker compose ps
Invoke-WebRequest -UseBasicParsing http://localhost:3000/api/health
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health
Invoke-WebRequest -UseBasicParsing http://localhost:8000/ready
Invoke-WebRequest -UseBasicParsing http://localhost:8000/api/v1/meta
```

The Phase 1 baseline at `baab8f7` remains verified by hosted run `29367040183`.
The Phase 2 runner adds migration `20260715_0003`, real private object/scanner
contracts, restricted async processing, deterministic score golden cases, and
registered/guest desktop/mobile workflows. Its local counts and security/build
results pass and are recorded in `PLANS.md`. Hosted run `29378312134` passed the
complete Phase 2 workflow on implementation commit `3b8d639`.
Phase 3 local closeout passed with `scripts/verify-phase3.ps1` on 2026-07-19:
format, lint, type, unit, build, container, migration, integration, runtime, and
isolated browser gates all passed. Hosted run `29657932938` then passed
supply-chain, API, web/contracts, worker, browser-smoke, Resume Health E2E,
Career Record E2E, and container/image jobs on the identical Phase 3 tree.
Phase 4 local closeout passed with `scripts/verify-phase4.ps1` on 2026-07-19:
format, lint, type, unit, build, container, migration, integration, runtime,
worker hardening, and isolated Role Explorer browser gates all passed.
Phase 5 local closeout passed with `scripts/verify-phase5.ps1` on 2026-07-19:
format, lint, type, unit, build, container, migration, integration, runtime,
worker hardening, and isolated Job Match browser gates all passed.
Phase 6 local closeout passed with `scripts/verify-phase6.ps1` on 2026-07-19:
format, lint, type, unit, build, container, migration, integration, runtime,
worker hardening, grounding/provider tests, and isolated Change Studio browser
gates all passed.
Phase 7 local closeout passed with `scripts/verify-phase7.ps1` on 2026-07-19:
format, lint, type, unit, build, container, migration, integration, runtime,
worker hardening, renderer/round-trip tests, and isolated Resume Builder browser
gates all passed.

## License and production use

No license or production deployment approval has been selected in Phase 0.
Treat the repository as private and non-production until those decisions, a
security review, data-processing terms, retention defaults, backup/restore tests,
and a protected deployment environment are complete.
