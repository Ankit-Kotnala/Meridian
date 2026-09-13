# Rezumi

**Your career. Verified. Elevated.**

Rezumi is a truth-locked career application operating system. A structured,
evidence-backed career profile is the source of truth; resumes, job-match
analyses, application packs, and interview prep are all **derived, reviewable
outputs** with machine-checkable provenance back to that evidence. Nothing
factual is invented, and no material change is applied without explicit review.

> Rezumi scores are internal, explainable readiness measurements — not employer
> or applicant-tracking-system scores, and not a guarantee of any outcome.

> **Status:** technical preview, private and non-production. See
> [PLANS.md](PLANS.md) for authoritative implementation status and evidence per
> phase — don't infer that a module exists from the architecture docs alone.

## Stack

| Layer     | Technology                                                                          |
| --------- | ----------------------------------------------------------------------------------- |
| Web       | Next.js 16 (App Router), React 19, TypeScript 5.9 strict, Tailwind CSS 4            |
| API       | Python 3.13, FastAPI, Pydantic, async SQLAlchemy + asyncpg                          |
| Worker    | Celery with a Redis broker/result backend                                           |
| Backend   | Shared `rezumi-backend` modular monolith (ports & adapters)                         |
| Contracts | FastAPI OpenAPI → generated TypeScript schema + typed client                        |
| Services  | PostgreSQL (pgvector), Redis, MinIO (S3), ClamAV, Mailpit                           |
| Tooling   | npm 11 + Turbo (JS), one uv workspace rooted at `backend/` (Python), Docker Compose |

## Repository map

```text
frontend/
  web/                Next.js UI (src/app routes + src/modules/<feature>)
  ui/                 Accessible React primitives
  design-tokens/      Shared visual tokens
  eslint-config/      Frontend boundary and lint rules
  typescript-config/  Shared strict TypeScript configs
  test-fixtures/      Explicitly fictional frontend/demo fixtures
backend/
  api/                Thin FastAPI delivery; adapters under modules/<context>
  worker/             Thin Celery delivery; task adapters under tasks/
  core/               Shared Python monolith (rezumi.foundation + rezumi.modules.*)
shared/
  contracts/          OpenAPI artifact, generated schema, typed client
docs/                 Product, architecture, security, scoring, ADRs
infra/                Local container infrastructure
scripts/              Cross-platform dev + verification scripts
```

## Prerequisites

- Docker Engine/Desktop + Compose v2 (enough memory for the full stack; ClamAV
  alone is configured for up to 2 GiB)
- Node.js 24 with Corepack
- Python 3.13 + uv
- GNU Make + a POSIX shell, **or** PowerShell with the checked-in `scripts/*.ps1`

## Quickstart

```sh
cp .env.example .env
make dev              # build + start the full Compose stack (attached)
```

Cross-platform / PowerShell:

```powershell
.\scripts\setup.ps1
npm run local:up      # detached, health-checked
npm run local:smoke   # probe web, API, Mailpit
```

Then create an account at `/register`, click the verification link captured in
[Mailpit](http://localhost:8025), and sign in at `/login`. A labeled fictional
preview is at `/demo/dashboard`. Local `.env` values are development-only.

**Host hot reload** (fastest UI/API iteration):

```powershell
npm run local:deps    # PostgreSQL, Redis, MinIO, Mailpit, ClamAV only
npm run dev:web       # Next.js on the host against dependency containers
npm run dev:api       # FastAPI on the host with reload
npm run dev:worker    # Celery worker on the host
```

When you run the web app **inside Docker** instead, rebuild the image after UI
changes: `npm run local:rebuild:web`.

### Local services

| Service       | URL                                                        |
| ------------- | ---------------------------------------------------------- |
| Web           | <http://localhost:3000>                                    |
| API docs      | <http://localhost:8000/docs>                               |
| API health    | <http://localhost:8000/health> · `/ready` · `/api/v1/meta` |
| MinIO console | <http://localhost:9001>                                    |
| Mailpit       | <http://localhost:8025>                                    |

## Workspace

Authenticated product UI is organized into **seven sidebar destinations**. Sections
with multiple tools also show a sub-navigation bar (for example Job search → Saved
jobs → Role matching). All routes below require a signed-in session unless noted.

| Destination     | Routes | What it does |
| --------------- | ------ | ------------ |
| **Home**        | `/dashboard` | Workspace overview and activation guidance |
| **Profile**     | `/career-profile`, `/evidence`, `/achievement-inbox`, `/career-profile/imports` | Career Record source of truth: roles, skills, evidence, imports, and achievement intake |
| **Resumes**     | `/resume-health/account`, `/resume-builder`, `/change-studio` | Upload and review resume health, build evidence-backed resume versions with verified exports, and apply grounded Change Studio suggestions |
| **Job search**  | `/job-match`, `/job-match/saved`, `/job-match/roles` | Browse a shared open-job catalog (paginated search with total counts), save listings to your jobs, analyze requirement coverage against eligible evidence, and compare role readiness. Legacy `/role-explorer` redirects to `/job-match/roles`. |
| **Applications**| `/applications` | Track applications with immutable job + resume version pins; board, table, and calendar views |
| **Interview prep** | `/interview-prep`, `/interview-prep/library`, `/networking` | Skill journey and curated skill library, grounded STAR stories and session prep, plus consent-gated networking CRM (no scraping or automated outreach) |
| **Growth**      | `/career-growth`, `/analytics` | Tabbed growth workspace: promotion preparation and skill-path standing, staged role roadmap, Career Health snapshots, goals/development/reviews, and small-cohort-suppressed analytics |

**Guest / utility routes**

| Route | Notes |
| ----- | ----- |
| `/resume-health/guest` | Short-lived guest upload and review flow (browser-scoped) |
| `/onboarding`, `/settings/*` | Setup guide and account settings (profile, security, sessions, privacy, billing, connections) |
| `/admin` | Admin console (when enabled for the account) |
| `/demo/*` | Explicitly labeled fictional demo fixtures only |

## Commands

Run the narrowest check while iterating, then the gates before claiming done.

```sh
npm run dev:web / dev:api / dev:worker   # host hot-reload against containers
npm run local:up / local:down            # start (health-checked) / stop, keep volumes
npm run local:rebuild:web / local:rebuild:backend  # after container-mode code changes
npm run local:logs -- api                # follow one service

make format-check                     # prettier + ruff format
make lint                             # eslint + boundary checks + ruff
make typecheck                        # tsc (all) + mypy
make test                             # unit tests (web, ui, api, worker, backend)
make test-integration                 # stack up + migrate + probes
make test-e2e                         # Playwright (requires full stack + Mailpit)
make contracts-check                  # OpenAPI / TS drift gate
make verify                           # full gate (all of the above + build)

make migrate                          # alembic upgrade head
make seed                             # migrate + idempotent fictional local data
```

On native Windows without Make, use the equivalents: `.\scripts\setup.ps1`,
`.\scripts\verify.ps1`, `.\scripts\security-scan.ps1`, and
`.\scripts\verify-phaseN.ps1` for per-phase gates. `make help` lists everything.

`make reset-db` and `make seed` are **local-only and destructive to dev data** —
never run against shared or production data.

Focused examples:

```sh
npm run test --workspace=@rezumi/web -- src/modules/job-match
npm run test:api
cd backend/core && uv run pytest tests/unit/test_job_match_service.py
```

## Guardrails

- The career profile and its evidence — not an uploaded resume — are the source
  of truth. Missing facts produce a question, never invented prose.
- Material edits require review, evidence visibility, and explicit user action;
  published/exported versions are immutable.
- Scores are deterministic and versioned; an LLM never supplies the final number.
- All data is ownership-scoped with server-side authorization; cross-user access
  returns the same not-found as an unknown ID.
- Uploads, imported URLs, and model output are untrusted input (MIME/signature
  validation, fail-closed malware scanning, SSRF-blocked imports, strict AI
  grounding). Raw resumes and job text are never logged or sent to analytics.

## Documentation

Read [AGENTS.md](AGENTS.md) before contributing. Key references:

- [Architecture](docs/architecture.md) · [Local development](docs/local-development.md)
- [Product requirements](docs/product-requirements.md) · [Design system](docs/product-design-system.md)
- [Security threat model](docs/security-threat-model.md) · [Scoring methodology](docs/scoring-methodology.md) · [AI grounding policy](docs/ai-grounding-policy.md)
- [API conventions](docs/api.md) · [ADRs](docs/adr/README.md)

## License

No license or production-deployment approval has been selected. Treat the
repository as private and non-production until those decisions, a security
review, data-processing terms, and a protected environment are complete.
