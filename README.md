# Meridian

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

| Layer     | Technology                                                               |
| --------- | ------------------------------------------------------------------------ |
| Web       | Next.js 16 (App Router), React 19, TypeScript 5.9 strict, Tailwind CSS 4 |
| API       | Python 3.13, FastAPI, Pydantic, async SQLAlchemy + asyncpg               |
| Worker    | Celery with a Redis broker/result backend                                |
| Backend   | Shared `rezumi-backend` modular monolith (ports & adapters)              |
| Contracts | FastAPI OpenAPI → generated TypeScript schema + typed client             |
| Services  | PostgreSQL (pgvector), Redis, MinIO (S3), ClamAV, Mailpit                |
| Tooling   | pnpm 11 + Turbo (JS), one root uv workspace (Python), Docker Compose     |

## Repository map

```text
apps/
  web/        Next.js UI (src/app routes + src/modules/<feature>)
  api/        Thin FastAPI delivery; adapters under modules/<context>
  worker/     Thin Celery delivery; task adapters under tasks/
packages/
  backend/    Shared Python monolith (rezumi.foundation + rezumi.modules.*)
  contracts/  OpenAPI artifact, generated schema, typed client
  ui/         Accessible React primitives
  design-tokens/, eslint-config/, typescript-config/, test-fixtures/
docs/         Product, architecture, security, scoring, ADRs
infra/        Local container infrastructure
scripts/      Cross-platform dev + verification scripts
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
pnpm local:up         # detached, health-checked
pnpm local:smoke      # probe web, API, Mailpit
```

Then create an account at `/register`, click the verification link captured in
[Mailpit](http://localhost:8025), and sign in at `/login`. A labeled fictional
preview is at `/demo/dashboard`. Local `.env` values are development-only.

### Local services

| Service       | URL                                                        |
| ------------- | ---------------------------------------------------------- |
| Web           | <http://localhost:3000>                                    |
| API docs      | <http://localhost:8000/docs>                               |
| API health    | <http://localhost:8000/health> · `/ready` · `/api/v1/meta` |
| MinIO console | <http://localhost:9001>                                    |
| Mailpit       | <http://localhost:8025>                                    |

## Features

All feature routes require an authenticated session unless noted.

| Area           | Route                                                | What it does                                                                                                          |
| -------------- | ---------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Career Record  | `/career-profile`, `/evidence`, `/achievement-inbox` | Owner-scoped experience, skills, and evidence with per-field provenance; evidence strength is separate from lifecycle |
| Resume Health  | `/resume-health/account`, `/resume-health/guest`     | Upload → scan → canonical review → deterministic analysis; guest flow is short-lived and browser-scoped               |
| Role Explorer  | `/role-explorer`                                     | Evidence-linked readiness analysis and role comparison                                                                |
| Job Match      | `/job-match`                                         | Extracts job requirements and compares them to eligible evidence                                                      |
| Change Studio  | `/change-studio`                                     | Grounded, reviewable suggestions with accept/reject/edit                                                              |
| Resume Builder | `/resume-builder`                                    | Evidence-backed drafts, immutable versions, verified exports                                                          |
| Applications   | `/applications`                                      | Pins immutable job + resume versions; board/table/calendar tracking                                                   |
| Interview Prep | `/interview-prep`                                    | Resume Defense Map + grounded STAR stories                                                                            |
| Networking     | `/networking`                                        | Private, consent-gated relationship CRM (no scraping or outreach)                                                     |
| Career Growth  | `/career-growth`                                     | Goals, reviews, and promotion-readiness prep                                                                          |
| Analytics      | `/analytics`                                         | Immutable, small-cohort-suppressed pattern snapshots                                                                  |
| Settings       | `/settings/*`                                        | Profile, security, sessions, consent, privacy, billing, connections                                                   |

## Commands

Run the narrowest check while iterating, then the gates before claiming done.

```sh
pnpm dev:web / dev:api / dev:worker   # host hot-reload against containers
pnpm local:up / local:down            # start (health-checked) / stop, keep volumes
pnpm local:logs -- api                # follow one service

make format-check                     # prettier + ruff format
make lint                             # eslint + boundary checks + ruff
make typecheck                        # tsc (all) + mypy
make test                             # unit tests (web, ui, api, worker, backend)
make test-integration                 # stack up + migrate + probes
make test-e2e                         # Playwright
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
