# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Rezumi: a "truth-locked" career application operating system. A structured,
evidence-backed career profile (`career_record`) is the source of truth; resumes,
job-match analyses, AI suggestions, and application packs are all derived,
reviewable outputs with machine-checkable provenance back to that evidence. This
invariant (never invent a fact; every generated claim must cite eligible
evidence) drives most architectural decisions in this repo — see `AGENTS.md`
before making product changes.

**Read `AGENTS.md` first.** It is the binding, repo-wide rule set (product
invariants, architecture boundaries, security/authz rules, workflow steps) and
takes priority over general conventions. `docs/architecture.md` is the detailed
target-architecture reference; `PLANS.md` is authoritative for what is actually
implemented vs. planned per phase — do not assume a module exists just because
`docs/architecture.md` or `docs/product-requirements.md` describes it.

## Repository layout

```text
apps/
  web/                 Next.js App Router UI (apps/web/src/app + src/modules/<feature>)
  api/                 Thin FastAPI HTTP delivery; adapters under modules/<bounded_context>
  worker/              Thin Celery delivery; task adapters under tasks/<bounded_context>.py
packages/
  backend/             Shared Python modular monolith (rezumi.foundation + rezumi.modules.<feature>)
  contracts/           OpenAPI artifact, generated TS schema, typed openapi-fetch client
  ui/                  Generic accessible React components (no product/route logic)
  design-tokens/       Shared visual tokens
  eslint-config/       Frontend lint + dependency-boundary rules (check-web-boundaries.mjs)
  typescript-config/   Shared strict TypeScript configuration
  test-fixtures/       Explicitly fictional fixtures only
docs/                  Product, architecture, security, API, scoring, ADRs
infra/                 Local container infrastructure (web-edge BFF, MinIO init)
scripts/               Cross-platform local dev + phase verification scripts
```

One root uv workspace (single lockfile) covers `apps/api`, `apps/worker`, and
`packages/backend`. Both apps depend on the backend; the backend imports neither
app, and the worker never imports the API. One root pnpm workspace (Turbo) covers
the JS packages.

### Backend module shape

Each `packages/backend/src/rezumi/modules/<feature>` follows a ports-and-adapters
layout: `domain` (framework-free entities/rules), `application` (services/ports),
`infrastructure` (SQLAlchemy repositories, providers implementing those ports),
plus module-owned `api`/`tasks` where relevant. `apps/api` and `apps/worker` are
thin adapters that call into `application` services — they must not contain
business rules or talk to another module's tables. Cross-module reads go through
an explicit application service/query/event, never direct table access.
Executable architecture tests (`packages/backend/tests/architecture`,
`packages/eslint-config/check-web-boundaries.mjs`) enforce these boundaries —
run them (`make test`, `pnpm lint`) after moving code across module lines.

Existing bounded contexts: `identity`, `resume_health`, `career_record`,
`role_readiness`, `job_match`, `change_studio`, `resume_builder`,
`application_workspace`, `interview_prep`, `networking`, `career_growth`,
`career_analytics`.

### Frontend module shape

Next.js route files under `apps/web/src/app` stay thin; product/domain UI and
state live under `apps/web/src/modules/<feature>`; framework-neutral reusable UI
lives in `packages/ui`. Feature modules must not deep-import another feature
module or import route files, and `src/shared` must not import routes or feature
modules — enforced by `pnpm architecture:check` (part of `pnpm lint`).

### Contracts

FastAPI's OpenAPI output is the authoritative wire contract. The normalized
artifact lives in `packages/contracts/openapi`; the generated TypeScript schema
and typed `openapi-fetch` client wrapper are generated from it. Never hand-edit
generated contract files or add parallel handwritten wire models — regenerate
instead (`pnpm contracts:generate`) and commit the result in the same change as
any API schema change. `pnpm contracts:check` / `make contracts-check` fails CI
on drift.

## Commands

Prereqs: Docker Engine/Desktop + Compose v2, Node.js 24 + Corepack, Python 3.13 +
uv, and either GNU Make or PowerShell (`scripts/*.ps1`). `make setup` / `.\scripts\setup.ps1`
installs pinned JS + Python deps and creates `.env` from `.env.example`.

### Local stack

```sh
make dev              # attached: build + start full Compose stack
pnpm local:up         # detached: build + start full stack, health-checked
pnpm dev:web          # host Next.js w/ hot reload against backend containers
pnpm dev:api          # host FastAPI w/ hot reload against dependency containers
pnpm dev:worker       # host Celery worker against dependency containers
pnpm local:rebuild:web       # rebuild web + web-edge images after a container-mode edit
pnpm local:rebuild:backend   # rebuild api/worker/scheduler images
pnpm local:smoke      # HTTP probes for web/API/Mailpit
pnpm local:down       # stop containers, preserve volumes
```

Host hot-reload (`dev:web`/`dev:api`/`dev:worker`) reflects source edits
immediately; a Docker-built service only sees source as of its last image build,
so rebuild the relevant image before testing a container-mode change.

### Quality gates (run narrowest first, then before claiming a task complete)

```sh
make format-check     # pnpm format:check + ruff format --check (backend/api/worker)
make lint             # pnpm lint (turbo + web boundary check) + ruff check
make typecheck        # pnpm typecheck (turbo) + mypy (backend/api/worker)
make test             # pnpm test (turbo + edge) + pytest (backend arch/unit, api, worker)
make test-integration # docker compose up + alembic upgrade + health probes + celery ping
make test-e2e         # pnpm test:e2e (Playwright, apps/web/e2e)
make contracts-check  # uv lock --check + pnpm contracts:check (OpenAPI/TS drift)
make verify           # contracts-check + format-check + lint + typecheck + test + build + compose-config + test-integration
```

Per-workspace/single-suite commands:

```sh
pnpm test:web                                            # apps/web vitest (all)
pnpm --filter @rezumi/web test -- <pattern>             # vitest, filtered
pnpm --filter @rezumi/web test:watch                    # vitest watch mode
pnpm --filter @rezumi/ui test                            # packages/ui vitest
pnpm test:api                                              # uv run pytest apps/api/tests
pnpm test:worker                                           # uv run pytest apps/worker/tests
pnpm test:backend                                          # uv run pytest packages/backend/tests/{architecture,unit}
cd packages/backend && uv run pytest tests/unit/test_job_match_service.py -k some_case  # single backend test
cd apps/api && uv run pytest tests/some_test.py::test_name                              # single API test
pnpm test:e2e -- --grep "some journey"                      # single Playwright spec (from apps/web)
```

Backend integration tests (real PostgreSQL/Redis/MinIO/ClamAV) live in
`packages/backend/tests/integration` and `apps/*/tests` integration marks; they
require the dependency containers running (`pnpm local:deps`) and fail rather
than silently skip when their dependency URLs are absent — do not treat that as
a passing/quarantined result.

### Per-phase E2E and verification

`make test-e2e-stack-phaseN` / `scripts/verify-phaseN.ps1` run an isolated
Playwright journey and the full gate for a given implementation phase (see
`docs/testing-strategy.md` for what each phase covers). `make verify-phaseN`
composes `make verify` with that phase's isolated journey. Use the highest
numbered phase relevant to the module you're touching.

### Migrations

```sh
make migrate          # alembic upgrade head (packages/backend/alembic.ini)
make seed             # migrate + idempotent fictional local seed (Phase 1-9 data)
```

Migrations live in `packages/backend/alembic`; keep exactly one Alembic head.
New tables must be owner-scoped (see Data/authz rules below) and match
registered SQLAlchemy metadata — architecture/migration tests catch drift.

## Non-obvious conventions worth knowing before editing

- **Ports and adapters are load-bearing, not decorative.** Domain code must never
  import FastAPI, SQLAlchemy, Redis, object storage, queue libraries, or provider
  SDKs. Provider-specific code (parsing, OCR, malware scanning, job-URL import,
  AI, billing, error monitoring) sits behind named ports (`ResumeParserProvider`,
  `MalwareScanner`, etc.); tests and local dev use deterministic fake adapters, no
  third-party credentials required.
- **Every user-owned row/object needs explicit ownership**, and repositories must
  fetch by ownership scope + resource ID together — never authorize on a bare ID
  match. Cross-user access returns the same not-found response as an unknown ID.
- **Evidence strength vs. lifecycle are independent.** Clients never set evidence
  strength (`Verified`/`Confirmed`/`Supported`/`Inferred`/`Unsupported`) directly;
  only specific server-side transitions can produce each value, and no
  `VerificationAuthority` provider is configured, so production cannot currently
  produce `Verified`.
- **AI/model output is untrusted input**, gated by strict schema validation and a
  deterministic grounding verifier before a user can even see it as acceptable;
  see `docs/ai-grounding-policy.md`. Numeric claims require confirmed/verified
  evidence with unit/period/attribution, not just a plausible-looking number.
- **Scores are deterministic and versioned**, never model-computed. See
  `docs/scoring-methodology.md` for the normative feature/weight definitions and
  the canonical internal-score disclaimer text that must appear anywhere a score
  could be misread as an employer/ATS score.
- **Uploads and imported URLs are hostile input by default** — MIME/signature
  validation, page/size/archive-expansion limits, randomized object keys,
  fail-closed ClamAV, HTTP(S)-only URL import with private/loopback address
  blocking. Don't relax these without reading the relevant section of
  `AGENTS.md`/`docs/architecture.md` first.
- **Don't create `common`/`helpers`/`misc`/`services`/`utils` dumping grounds** on
  either side of the stack; put code in its owning module.
- **Don't create empty scaffolding** for a future phase (empty module dirs, unused
  Terraform, reserved routes) — only add a directory when its owning phase has
  real implementation/test content.
- Pinned dependencies are changed through `pnpm`/`uv` with lockfiles committed —
  don't hand-edit `pnpm-lock.yaml`/`uv.lock`, and avoid preview/prerelease
  dependencies without an ADR.

## Where to look for more detail

- `AGENTS.md` — binding repo-wide rules (product invariants, security, authz,
  workflow). Read before any non-trivial change.
- `docs/architecture.md` — full target architecture, per-module boundary
  descriptions, request/job flow diagrams.
- `docs/testing-strategy.md` — test layers, per-phase coverage expectations,
  fixture matrix, CI tiers.
- `docs/local-development.md` — "where to make a change" table mapping change
  type to primary location and focused check.
- `docs/scoring-methodology.md` / `docs/ai-grounding-policy.md` — normative
  scoring formulas and AI grounding rules.
- `docs/adr/` — accepted architectural decisions; add a new ADR before
  introducing a competing framework or architectural path.
- `PLANS.md` — authoritative current implementation/verification status per
  phase; do not infer that something is implemented from architecture docs alone.
