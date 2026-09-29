# Meridian

**Your career. Verified. Elevated.**

Truth-locked career OS: the **Career Record and evidence graph** are the source
of truth. Resumes, job-match analyses, application packs, and interview prep are
derived outputs with reviewable provenance — never invented facts, never silent
changes.

> Scores are internal readiness signals, not employer/ATS scores or outcome
> guarantees. **Technical preview only** — see [PLANS.md](PLANS.md) for what is
> actually implemented (not just described in architecture docs).

> **Repository note:** `rezumi` remains the internal package, service, and
> environment-variable namespace while the Meridian rename is rolled out. These
> identifiers are implementation details, not a second product.

## Stack

| Layer        | Tech                                                    |
| ------------ | ------------------------------------------------------- |
| Web          | Next.js 16, React 19, TypeScript, Tailwind 4            |
| API / worker | Python 3.13, FastAPI, Celery                            |
| Backend      | `backend/core` modular monolith (ports & adapters)      |
| Data         | PostgreSQL, Redis, MinIO, ClamAV, Mailpit               |
| Contracts    | OpenAPI → generated TS client (`shared/contracts`)      |
| Tooling      | npm + Turbo, uv workspace at `backend/`, Docker Compose |

```text
frontend/web          routes + feature modules
frontend/ui           shared accessible components
backend/api           thin HTTP delivery
backend/worker        thin Celery delivery
backend/core          domain, migrations, integrations
shared/contracts      wire contract artifacts
docs/                 product, architecture, ADRs
```

## Prerequisites

Docker Compose v2 · Node 24 + Corepack · Python 3.13 + uv · Make **or** PowerShell (`scripts/*.ps1`)

## Quickstart

```sh
cp .env.example .env
make dev                    # full stack, attached logs
```

```powershell
.\scripts\setup.ps1
npm run local:up            # detached + health-checked
npm run local:smoke
```

Register at `/register` → verify via [Mailpit](http://localhost:8025) → sign in.
Fictional demo: `/demo/dashboard`.

**Fast iteration (host reload):**

```powershell
npm run local:deps          # DB, Redis, MinIO, Mailpit, ClamAV
npm run dev:web             # or dev:api / dev:worker
```

Container-mode UI changes need `npm run local:rebuild:web`.

| Service | URL                                                 |
| ------- | --------------------------------------------------- |
| Web     | <http://localhost:3000>                             |
| API     | <http://localhost:8000/docs> · `/health` · `/ready` |
| MinIO   | <http://localhost:9001>                             |
| Mailpit | <http://localhost:8025>                             |

## Product map

Seven sidebar destinations (sub-nav where noted). Authenticated unless marked guest.

| Area           | Entry                                                           | Purpose                                                                              |
| -------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Home           | `/dashboard`                                                    | Workspace overview                                                                   |
| Profile        | `/career-profile` · Evidence · Achievement Inbox · Imports      | Career Record + provenance                                                           |
| Resumes        | `/resume-health/account` · `/resume-builder` · `/change-studio` | Health review, versioned exports, grounded edits                                     |
| Job search     | `/job-match` · `/saved` · `/roles`                              | Paginated catalog, save & analyze jobs, role readiness (`/role-explorer` → `/roles`) |
| Applications   | `/applications`                                                 | Track packs; board / table / calendar                                                |
| Interview prep | `/interview-prep` · `/library` · `/networking`                  | Skill path, library, STAR prep, private CRM                                          |
| Growth         | `/career-growth` · `/analytics`                                 | Promotion prep, roadmap, Career Health, goals, analytics                             |

Guest: `/resume-health/guest`. Utility: `/settings/*`, `/onboarding`, `/admin`, `/demo/*`.

## Commands

Iterate narrow, then gate before calling work done.

```sh
make lint && make typecheck && make test    # usual pre-PR loop
make verify                                 # full Phase 0 gate
make test-integration && make test-e2e      # stack + Playwright (needs Mailpit)

make migrate && make seed                   # local DB only — destructive reset: make reset-db
```

Common shortcuts:

```sh
npm run dev:web
npm run local:up / local:down
npm run local:rebuild:web
npm run test --workspace=@rezumi/web -- src/modules/<feature>
npm run contracts:check
```

Windows without Make: `.\scripts\setup.ps1`, `.\scripts\verify.ps1`, `make help`.

## Continuous integration

GitHub Actions runs the quality, contract, API, worker, browser, container, and
supply-chain checks for pull requests and pushes to `main` and `development`.
You can also start the workflow manually from the Actions tab. CI uses Node 24,
npm 11.8.0, Python 3.13, and uv 0.11.21; run the commands above locally before
opening a pull request.

## Guardrails

- Evidence-backed profile is truth; gaps become questions, not prose.
- Material changes need explicit review; published versions are immutable.
- Scores are deterministic and versioned — not model-generated.
- Every row is owner-scoped; cross-user IDs return not-found.
- Uploads, URLs, and model output are hostile until validated and grounded.

## Docs

Start with [AGENTS.md](AGENTS.md). Then [architecture](docs/architecture.md),
[local development](docs/local-development.md), [scoring](docs/scoring-methodology.md),
[AI grounding](docs/ai-grounding-policy.md), [security](docs/security-threat-model.md),
[API](docs/api.md), [cloud-portable demo deployment](docs/cloud-demo-deployment.md),
[ADRs](docs/adr/README.md).

## License

Private, non-production. No license or deployment approval selected yet.
