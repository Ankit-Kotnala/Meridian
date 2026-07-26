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

**Phase 2 typed semantic parsing/review and Resume Health v2 closure is
implemented and locally verified, including its separate security gate; hosted
closure evidence remains pending authorization to publish. Phase 8 is hosted
verified in PR #21 and Phase 9 in PR #22.** Phases 0 through 7 retain their
historical hosted evidence; PR #20 merged Phases 5 through 7 after hosted CI run
`30119088488` passed every required job. Phase 8 implementation revision
`964cd9c` passed the consolidated local gate and separate security scan on
2026-07-24; PR #21 runs `30126993025` and `30128304892` passed every required
hosted job. The repository uses a
shared Python modular monolith, one root uv workspace, generated API contracts,
thin deployable applications, and executable dependency boundaries.

Hosted CI run `29657932938` passed every Phase 3 job on no-change trigger commit
`f752b55`, whose tree is identical to implementation commit `0df8bcf`; prior
Phase 2 evidence remains preserved at `3b8d639` and run `29378312134`. The
latest predecessor baseline is merge commit `f9807dc` from PR #20.

See [PLANS.md](PLANS.md) for current status, historical evidence, and phase gates.
Do not infer that a planned endpoint or module is implemented from the
architecture documents.

## Stack

- Web: Node.js 24, pnpm 11.13.0, Next.js 16.2.11 App Router, React 19.2.7,
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
`/onboarding`, `/settings`, `/settings/profile`, `/settings/security`,
`/settings/sessions`, `/settings/consent`, `/settings/notifications`,
`/settings/privacy`, `/settings/connections`, `/settings/billing`,
`/career-profile`, `/career-profile/imports`, `/evidence`, and
`/achievement-inbox` require an authenticated session. The labeled fictional
preview remains available at `/demo/dashboard`; it is isolated from real account
state.

Career Profile is independent of resume upload. It stores user-owned experience,
typed career items, and skills with year/month precision, explicit grouping,
optimistic concurrency, explicit confirmation, per-field provenance, personal
facts, experience-to-project relationships, and reviewable typed import
proposals. Resume import reads the owner-scoped reviewed semantic snapshot; it
does not let the browser author resume-derived facts or silently overwrite the
Career Record.
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

Resume Builder is available at `/resume-builder`. Its existing web workflow
continues to create evidence-backed drafts and immutable versions from the
owner-scoped Career Record and optional Change Studio output. This backend-only
closure adds additive source/layout/fact contracts without adding frontend
behavior. PDF/DOCX/text/JSON export returns durable `202` state; an isolated
worker renders and independently re-parses the output against one exact
cross-format fidelity manifest. Omissions, duplications, order/searchability
failures, page overflow, unsupported facts or numbers, and version/hash drift
block download. Every attempt creates a durable deletion backstop before its
private-object write, so a crash or uncertain write cannot strand an
unreferenced file. Verified files atomically cancel that backstop and use
short-lived owner-checked download intents plus durable fenced deletion.

Application Workspace is available at `/applications`. It creates owner-scoped
application records from one exact saved-job revision and one immutable resume
version, then pins the job version/source hash and requirement snapshot, validates
the resume version's per-claim hash ledger, and copies exact eligible evidence
revision numbers and statement hashes. It provides accessible board, table, and
calendar views; explicit
non-drag stage changes; contacts, deadlines, follow-ups, tasks, notes, events,
outcomes, rejection reasons, and offer summaries; and deterministic grounded
application packs with consistency findings. Legacy resume sources without the
complete immutable claim/evidence ledger are refused. The product does not submit
applications or send messages on the user's behalf.

Interview Prep is available at `/interview-prep`. It derives a Resume Defense
Map from one owner-authorized Application Workspace snapshot, stores structured
STAR stories, and supports role-specific questions, mock sessions, private
notes/reflections, and grounded follow-up drafts. A ready or generated factual
story must pin every STAR field to exact application claims and eligible evidence
revisions; unsupported numbers are refused. Before a new question bank or
follow-up draft is generated, the stored session pins are rechecked against live
Career Record eligibility and the exact current evidence revision. Revised,
revoked, downgraded, unavailable, conflicted, or otherwise ineligible evidence
fails closed. An exact idempotent replay returns its existing immutable output
rather than regenerating historical text. Drafts may remain incomplete, and no
follow-up is sent by CareerOS.

Networking is available at `/networking`. It is a private, owner-scoped CRM for
organizations, contacts, relationship stages, tags, notes, interactions,
referrals, reviewed templates, and local reminders. Contact collection, storage,
and outreach use a dedicated purpose-specific attestation ledger. CareerOS does
not treat account consent or Application Workspace contacts as third-party
consent, and it does not scrape, import, or deliver outreach. Withdrawing consent
for collection or storage irreversibly tombstones the contact and redacts all
contact-child personal/free-text content; only content-free consent, audit, and
queue state remains where required. Withdrawing outreach alone preserves the
contact, private notes, and inbound/mutual history while cancelling local work
and redacting outbound/template/referral/reminder material. Owner/contact
collection limits and bounded safe reminder history prevent unbounded storage.
Consent policy identifiers are fixed by the server and constrained again in the
database, so arbitrary user/contact text cannot enter the retained ledger.

Career Growth is available at `/career-growth`. Goals, milestones, development
plans, learning/certification and internal-mobility preparation, evidence-backed
quarterly/annual reviews, and annual resume-refresh tracking use exact current
Career Record evidence pins. Live insights derive current eligible achievement
history and skill-evidence coverage without copying a second source of truth.
Completed-promotion, completed-milestone, finalized-review, and completed
annual-refresh insight checks count or expose a stored link only while its exact
revision number, hash, and revision timestamp still match the current eligible
evidence. Promotion Readiness is a six-check preparation report, not an employer
decision or forecast. Career Health v1 is a deterministic longitudinal
maintenance measure with strict insufficient-data behavior and the canonical
score disclaimer.

Career Analytics is available at `/analytics`. Durable owner-scoped refresh jobs
produce timezone-specific immutable snapshots for application stages, outcomes,
rates, role/industry/source breakdowns, exact resume-version patterns,
requirement-coverage trends, eligible achievement growth, and Role Readiness
history. Reports expose versioned metric/cohort/timestamp definitions, suppress
rates and averages below five records, fail stale or tampered snapshots closed,
and describe correlations only. Achievement growth is re-evaluated through the
canonical Career Record eligibility policy; application event buckets use only
the selected application cohort; and the bounded Role Readiness/achievement
point set is hashed for the exact guarded source window used by the refresh.
The public window remains bounded to a 3,650-day delta; internal Career Record
and Role Readiness reads allow only the additional day on each side required
for timezone-safe UTC selection. API and worker composition use the same owned
Resume Health and clean-attachment status queries when re-evaluating evidence.
Raw resume, evidence, contact, note, offer, rejection, and generated-document
prose are excluded.

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
make test-e2e-stack-phase8 # isolated Phase 8 desktop/mobile Application Workspace journeys
make test-e2e-stack-phase9 # isolated Phase 9 desktop/mobile career workspace journeys
make security-scan    # scan source, dependencies, app images, and trusted edge runtime
make migrate          # apply the current database migrations
make seed             # migrate and idempotently seed fictional local Phase 1-9 data
make verify           # full format/lint/type/test/contract/build/runtime gate
make verify-phase1    # full gate plus isolated Phase 1 integration/E2E
make verify-phase2    # full gate plus isolated Resume Health integration/E2E
make verify-phase3    # full gate plus isolated Career Record integration/E2E
make verify-phase4    # full gate plus isolated Role Explorer integration/E2E
make verify-phase5    # full gate plus isolated Job Match integration/E2E
make verify-phase6    # full gate plus isolated Change Studio integration/E2E
make verify-phase7    # full gate plus isolated Resume Builder integration/E2E
make verify-phase8    # full gate plus isolated Application Workspace integration/E2E
make verify-phase9    # full gate plus isolated Phase 9 career workspace integration/E2E
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
Use `.\scripts\verify-phase7.ps1` for the Phase 7 base migration
`20260719_0008` plus closure heads `20260726_0012`/`20260726_0013`, Resume
Builder repository/S3 integration, durable worker and fidelity tests, and the
existing authenticated Resume Builder export/download browser journey backed by
confirmed career evidence. Frontend editor extensions are outside this gate.
Use `.\scripts\verify-phase8.ps1` for migration `20260724_0009`, Application
Workspace repository integration, immutable-source and consistency tests, and
the complete desktop/mobile create/track/generate workflow. The final local
Phase 8 run passed on 2026-07-24; PR #21 runs `30126993025` and `30128304892`
passed every required hosted job. Use `.\scripts\verify-phase9.ps1` for migration
`20260724_0010`, its four product contexts, durable analytics/local-reminder
workers, and the Phase 9 desktop/mobile career workspace journey.
The cross-phase resume-ready closure adds migration `20260726_0011`; the Phase 1
and Phase 3 verifiers now exercise that head while rolling back to their
respective predecessor checkpoints.

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
Phase 7 closure migration `20260726_0012` adds pinned layout, confirmed personal
and entity display facts, canonical fidelity hashes/reports, durable render
leases/retry/dead-letter state, and the transactional export outbox. Migration
`20260726_0013` adds operation-typed outbox delivery plus separate fenced,
retryable private-object cleanup states and pre-write attempt-object backstops,
so deletion is never reported before storage confirms it and a worker crash
cannot lose cleanup intent. Inconsistent legacy `deleted` rows are recovered to
queued deletion without inventing timestamps or discarding object keys. Their
downgrades refuse incompatible live durable state.
Phase 8 migration `20260724_0009` adds owner-scoped applications, exact immutable
source pins, workflow events, tasks, notes, packs, generated documents,
idempotency records, and redacted audit events. It also forward-adds a nullable
all-or-none evidence-revision tuple to Change Studio claims without rewriting the
shipped Phase 6 migration: existing claims remain readable but explicitly
unpinned and cannot seed grounded Resume Builder/Application Workspace output;
new claims require complete pins. Downgrading to `20260719_0008` deletes Phase 8
workspace data and removes those forward-added fields; it is a
test/forward-repair path, not a production rollback recommendation.
Phase 9 migration `20260724_0010` adds owner-scoped Interview Prep, Networking,
Career Growth, and Career Analytics records, including exact evidence pins,
append-only contact consent, immutable review/score snapshots, and durable
analytics/reminder state. Composite constraints and database validation enforce
Growth target ownership, exact evidence revision number/timestamp/hash
provenance on every evidence-link insert or mutation, the immediate
review-predecessor chain, and the review's latest version ID/number/status tuple.
Networking reminder occurrences and outbox entries persist the same validated
trace ID for worker audit correlation. Analytics jobs and snapshots persist their
IANA timezone as part of identity. The migration conditionally repairs a pre-release
Phase 8 development database missing its canonical provenance tuple/check or
resume-change event/audit enum values without changing migration
`20260724_0009`. Downgrading to `20260724_0009` deletes Phase 9 data but
preserves those canonical Phase 8 objects.
Resume-ready closure migration `20260726_0011` adds owner-scoped entity and skill
confirmations, personal/contact facts, typed semantic import proposals,
experience-to-project relationships, and per-field provenance. Its constraints
prevent cross-owner links and more than one primary fact of a given kind.
Historical career entities are not silently marked confirmed. Downgrading to
`20260724_0010` removes only the closure tables; it is a test/forward-repair path,
not a production rollback after users create those records.
`make seed` starts only local PostgreSQL/MinIO prerequisites, applies migrations,
and runs the profile-gated seed container. Native PowerShell users can run
`.\scripts\seed-local.ps1`. The command writes an explicitly fictional,
provenance-valid graph across Phases 1 through 9 plus its private source and
verified-export objects. Stable UUIDs, immutable-row checks, and existing-object
verification make replays deterministic and non-destructive.

The seed refuses dependency I/O unless the environment is explicitly
`development`, an exact one-command confirmation is present, the database uses
the local `careeros` identity/database on an allowlisted Compose/loopback host,
the object endpoint is local MinIO, the bucket is `careeros-documents`, and the
database is at reviewed migration head `20260726_0013`. The fresh fixture
credential is printed only when the account is first created.
`pnpm fixtures:preview` remains a no-I/O presentation fixture and is not
evidence of persisted product state.

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

Local Compose publishes a dedicated minimized `web-edge` image, not the Next.js
container. Both shipped Node runtimes remove npm, Corepack, and other
package-manager executables after building. The edge replaces all client-selected
forwarding headers with its socket peer before the otherwise unexposed web BFF
signs an opaque source key for pre-authentication and guest-intake API abuse
controls. This is a local single-hop contract; a cloud load balancer requires an
explicit allowlisted trusted-hop design rather than accepting arbitrary forwarded
addresses.

Read [AGENTS.md](AGENTS.md) before contributing. The principal references are:

- [Documentation index](docs/README.md)
- [Architecture](docs/architecture.md)
- [Product requirements](docs/product-requirements.md)
- [Product design system](docs/product-design-system.md)
- [Visual QA matrix](docs/visual-qa-matrix.md)
- [Security threat model](docs/security-threat-model.md)
- [Scoring methodology](docs/scoring-methodology.md)
- [AI grounding policy](docs/ai-grounding-policy.md)
- [API conventions](docs/api.md)
- [Implementation checklist](docs/implementation-checklist.md)
- [Architecture decisions](docs/adr/README.md)

## Verification status through Phase 2 semantic closure and Phase 9

Phases 0 through 8 have recorded local and hosted evidence. Phase 8's complete
closeout evidence, including PR #21 workflow runs `30126993025` and
`30128304892`, is recorded in `PLANS.md`.
Phase 9's final-tree consolidated local gate, separate security scan, and hosted
PR #22 workflow run `30161489265` pass as recorded in `PLANS.md`.
The current Phase 2 closure adds typed semantic entities/fields and provenance,
typed immutable review operations, killable parser subprocess isolation,
independent extraction/layout/parser ports, Resume Health v2, and the expanded
adversarial fixture corpus. Its final local and security evidence is recorded in
`PLANS.md`; hosted evidence is not claimed before an authorized closure PR
passes.
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
.\scripts\verify-phase8.ps1
.\scripts\verify-phase9.ps1
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
registered/guest desktop/mobile workflows. Historical hosted run `29378312134`
passed the original generic-block v1 slice on implementation commit `3b8d639`.
The current semantic/v2 closeout uses the same exact runner plus a separate
security scan. Both local gates pass on the 2026-07-26 implementation tree; exact
results and the pending hosted-authorization boundary are recorded in
`PLANS.md`.
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
gates all passed. PR #20 subsequently merged the Phase 5–7 stack at `f9807dc`
after hosted CI run `30119088488` passed every required job.
That evidence remains the historical vertical-slice baseline. The 2026-07-26
Phase 7A/B/C closure replaces synchronous rendering and shared template
structure; its current verification evidence is recorded in `PLANS.md`.
Phase 8 local closeout passed on implementation revision `964cd9c` on
2026-07-24. `scripts/verify-phase8.ps1` exited 0 in 273 seconds with `206 passed`
in the backend portfolio, `104 passed` in the API portfolio, and `121 passed`
across 35 web test files. The production web build emitted 39 routes. A fresh
database reached migration `20260724_0009`, downgraded to `20260719_0008`, and
repaired forward; integration, worker, and container probes passed. Playwright
discovered 16 tests and finished with 10 passed and 6 intentional inherited
mobile skips, while Application Workspace itself passed its complete desktop and
mobile journeys.

Closeout hardening keeps migration `20260719_0007` immutable, refuses unpinned
legacy grounding sources, aligns database enums with the domain, makes resume
changes one real transaction, keeps omitted event-time retries idempotent,
rejects non-ASCII cursors, and reloads authoritative UI state safely after
conflicts. The separate `scripts/security-scan.ps1` exited 0 in 287.7 seconds:
Gitleaks was clean; pnpm and pip audits found no known vulnerabilities
(unpublished local workspace packages were skipped); API and worker had no
fixable-high findings; and web plus `web-edge` had no vulnerabilities. Three
medium Python-runtime findings remain with fixes available only in Python 3.15
prereleases, so they are nonblocking under the documented policy and remain
tracked. PR #21 workflow runs `30126993025` and `30128304892` passed every
required hosted job.

Phase 9 local closeout passed on 2026-07-25. The consolidated gate reported
`365 passed` for the backend portfolio, `134 passed` for the API portfolio,
`84 passed` for the worker portfolio, and `150 passed` across 43 web test files;
the production build emitted 48 routes. The isolated PostgreSQL suite passed 39
tests with 7 inherited SQLAlchemy cycle warnings. Playwright completed 12 tests
with 6 intentional inherited mobile skips, and the Phase 9 desktop and mobile
journeys both passed. Regression coverage isolates each interview story's stale
support; returns immutable delayed-replay results for STAR-story creation and
career-review finalization; narrows Networking's application lookup to a
content-free ID/stage reference; keeps Analytics aliases exactly equal to the
generated wire contracts; gives an explicitly reactivated reminder a fresh
occurrence/outbox without reviving redacted content; and ensures Analytics
dead-letter or expired-lease recovery cannot leave an orphaned queued job.

The final security gate is also green: Gitleaks, `pnpm audit`, and `pip-audit`
reported no actionable source or application-dependency finding, and the web and
`web-edge` images had no vulnerability. The newly disclosed
`brace-expansion` advisory is resolved by a workspace-wide `5.0.8` override plus
compatibility patches for the pinned minimatch 3.1.5 and 5.1.9 consumers. API
and worker now use the digest-pinned Python 3.13.14 Alpine 3.24 runtime with
OpenSSL 3.5.7, removing the newly disclosed fixable OpenSSL findings from the
older slim image. They retain only `CVE-2025-15366`, `CVE-2025-15367`, and
`CVE-2026-12003`, three nonblocking medium CPython 3.13.14 runtime findings whose
listed fixes are available only in Python 3.15 prereleases. PR #22 workflow run
`30161489265` passed every required hosted job at implementation/merge head
`1454792`.

## Phase 9 limitations and boundaries

- Networking consent records the account owner's explicit attestation; it is not
  independent proof supplied by the third party.
- Interview questions and follow-up drafts are deterministic and review-only.
  No production model provider or external delivery connector is enabled.
- Achievement history contains only current eligible Career Record evidence of
  type `achievement`; revoked, unsupported, deleted, and unrelated evidence is
  excluded.
- Annual resume refresh is an evidence-backed planning and completion workflow.
  It does not silently rewrite, publish, or export a resume.
- Promotion Readiness is a current preparation checklist, not an employer
  assessment, hiring probability, promotion guarantee, or measure of job-market
  value.
- Analytics depends on recorded workflow events, applies the selected IANA
  timezone, suppresses small cohorts, and reports observed patterns rather than
  causal effects.
- Account-wide export/deletion retention, load/soak evidence, backup/restore,
  production provider/region selection, and protected deployment remain Phase 10
  work.
- Resume Builder now has durable render/cleanup workers, five distinct
  constrained layouts, and a canonical blocking cross-format fidelity manifest.
  Rich graphics-heavy/multi-column templates remain intentionally unsupported
  until they can pass the same searchable exact-order corpus.
- The guarded seed is strictly local development tooling. It is not an import,
  backup restore, migration substitute, production bootstrap, or source of real
  career claims.

## License and production use

No license or production deployment approval has been selected in Phase 0.
Treat the repository as private and non-production until those decisions, a
security review, data-processing terms, retention defaults, backup/restore tests,
and a protected deployment environment are complete.
