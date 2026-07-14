# CareerOS implementation plan

Last updated: 2026-07-14  
Plan owner: engineering  
Current status: **Phase 0 complete in the working tree; Phase 1 not started;
hosted CI rerun required after the next commit**

## Status legend

- `[ ]` not started
- `[~]` in progress or implemented but not yet verified
- `[x]` implemented and verified in the current working tree
- `[!]` blocked; the blocker and evidence must be recorded

No phase is complete until every exit gate passes. A skipped check is not a pass.

## Repository assessment

The initial inspection on 2026-07-14 found `G:\Resumi` empty: no Git metadata,
README, agent instructions, package manifests, source, migrations, environment
files, configuration, or tests. There was therefore no existing implementation
to preserve and no code-level conflict to resolve. The attached reference image
is a visual-direction artifact, not a source of product claims or production
data.

Consequences:

- All architecture is greenfield, but every dependency and provider choice must
  still be explicit and reversible.
- There is no baseline test result or deployment compatibility history.
- Git was initialized on `main` during Phase 0. The repository's license remains
  an owner decision.
- Phase 0 established real health checks and test runners before subsequent work
  can claim a stable foundation.

See `docs/repository-assessment.md` for the complete assessment, assumptions, and
specification tensions.

## Phase 0 scope and status

### Included

- [x] Repository assessment and explicit assumptions
- [x] Repository rules, phase plan, setup documentation, architecture, product,
      security, scoring, grounding, API, testing, and ADR documentation
- [x] pnpm monorepo and Python project skeletons
- [x] Next.js web skeleton and accessible initial visual system
- [x] FastAPI liveness, dependency readiness, and safe metadata endpoints
- [x] Celery worker and deterministic health task
- [x] PostgreSQL/pgvector, Redis, and MinIO local services
- [x] Shared contracts/configuration/test-fixture package boundaries
- [x] Dockerfiles, Compose, `.env.example`, and Make command interface
- [x] CI foundation, formatting, lint, type checking, and initial tests
- [x] Cross-service health verification

All Phase 0 scope and repository-wide exit gates passed on 2026-07-14. Phase 1
remains intentionally unstarted. The latest hosted CI run targets the earlier
initial commit; its two failures are fixed and reverified locally but cannot be
rerun against uncommitted work.

### Explicitly deferred

- Authentication, authorization flows, onboarding, and protected routes (Phase 1)
- Domain tables and migrations beyond connection/migration infrastructure
- Upload, malware scanning, parsing, OCR, and resume scoring (Phase 2)
- Career profile, evidence persistence, and achievement capture (Phase 3)
- Role/job analysis and all production AI calls (Phases 4–6)
- Resume editing/export, application tracking, interview/networking/growth,
  billing, admin, and production deployment (Phases 7–10)
- Real customer testimonials, autonomous job submission, production secrets, and
  production data

The Phase 0 dashboard is an unauthenticated, clearly labeled fictional preview.
It must not imply that authentication, persisted metrics, or product analysis is
implemented.

### Phase 0 dependencies

```text
Pinned toolchains + env contract
          |
          +--> PostgreSQL/Redis/MinIO --> API readiness
          |                 |
          |                 +---------> Celery health
          |
          +--> shared workspace/config --> web + API + worker builds
                                      |
                                      +--> Compose health + CI verification
```

The verification gate depends on all branches. Documentation can be reviewed in
parallel but cannot turn a failing runtime gate green.

### Verification commands

The following command interface was exercised during integration; the recorded
results are under “Phase 0 evidence”:

```sh
make setup
make dev
docker compose config --quiet
docker compose ps
curl --fail http://localhost:3000/api/health
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ready
curl --fail http://localhost:8000/api/v1/meta
docker compose exec worker python -m careeros_worker.healthcheck
make format-check
make lint
make typecheck
make test
make verify
```

The worker health command uses Celery remote control through the broker and checks
that the running worker can respond; the registered deterministic task is
`careeros.worker.health.ping`.

### Phase 0 evidence

Evidence captured through 2026-07-14 22:20 IST against the current working tree:

| Command / gate                        | Result | Evidence                                                                                                                                     |
| ------------------------------------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Repository inventory                  | Pass   | Empty workspace observed before implementation; Git initialized on `main`                                                                    |
| `make setup`                          | Pass   | Clean Linux Node 24/uv image completed the Make target; native `scripts/setup.ps1` also completed with frozen lockfiles                      |
| `make dev` runtime path               | Pass   | Its `docker compose up --build` path was built and started with detached wait; all six services became healthy                               |
| `docker compose config --quiet`       | Pass   | Compose configuration rendered without errors                                                                                                |
| Runtime health probes                 | Pass   | Web health, API liveness/readiness, and metadata returned HTTP 200                                                                           |
| Dependency failure/recovery           | Pass   | API readiness returned HTTP 503 with PostgreSQL stopped and HTTP 200 after recovery                                                          |
| Migration and queue health            | Pass   | Alembic revision `20260714_0001`, pgvector 0.8.5, and Celery broker-backed ping verified                                                     |
| Format, lint, and type checks         | Pass   | Prettier, Ruff, strict TypeScript, and mypy completed with exit code 0                                                                       |
| Unit tests                            | Pass   | Web 9, contracts 6, API 19, and worker 12 tests passed                                                                                       |
| Production build and browser checks   | Pass   | Next.js built 20 routes; Playwright passed 7 checks with 1 intentional project-specific skip across desktop and mobile                       |
| Security and dependency scans         | Pass   | Gitleaks and dependency audits passed; Grype's fixable-high gate passed with two version-bound exceptions documented in `.grype.yaml`        |
| `make verify` / PowerShell equivalent | Pass   | The Make command graph was validated; `scripts/verify.ps1` completed the full non-runtime gate with exit code 0                              |
| Hosted CI                             | Rerun  | Initial-commit run 29349892186 failed formatting and env-isolation checks; both are fixed locally, while browser/container jobs pass locally |

## Roadmap and phase gates

| Phase                                                       | Outcomes                                                                                                                           | Depends on  | Exit evidence                                                                                          |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------ |
| Phase 0 — Foundation                                        | Monorepo, local dependencies, web/API/worker skeletons, contracts, health, CI, docs                                                | None        | Setup/dev work; all services healthy; format, lint, types, tests pass                                  |
| Phase 1 — Auth, shell, onboarding                           | Registration/verification/login/logout/reset, secure sessions, protected responsive shell, onboarding, dashboard/settings skeleton | Phase 0     | Auth journeys pass; anonymous/cross-user denial tests; accessible shell matches visual direction       |
| Phase 2 — Upload, parsing, general health                   | Secure PDF/DOCX pipeline, local provider, canonical resume, parse review, deterministic health report, guest/save flows            | Phase 1     | Fixtures parse; malformed uploads fail safely; scores reproduce and explain; correction works          |
| Phase 3 — Career profile, Evidence Vault, Achievement Inbox | Independent career CRUD, provenance graph, evidence states/attachments, guided capture and conflict checks                         | Phases 1–2  | Ownership/provenance tests; unsupported evidence excluded; user can maintain profile without resume    |
| Phase 4 — Role Explorer                                     | Role taxonomy/search/save/compare and deterministic evidence-linked readiness                                                      | Phase 3     | Role comparison works without job description; score and gaps explainable                              |
| Phase 5 — Job Match and prioritizer                         | Safe paste/URL import, source-spanned requirements, match matrix, hard gaps, application priority                                  | Phases 3–4  | SSRF tests; every requirement traceable; each match evidenced or missing/unknown; deterministic scores |
| Phase 6 — Change Studio and truth-locked AI                 | Provider gateway/fake, structured suggestions, grounding, review/diff actions, immutable versions, questions                       | Phases 3, 5 | Unsupported claims blocked; numbers grounded; user approval and adversarial injection tests pass       |
| Phase 7 — Resume builder and verified export                | Structured editor, five templates, PDF/DOCX/text, versions, re-parse and verification report                                       | Phases 2, 6 | Searchable exports round-trip critical fields; broken outputs blocked/warned; accessibility passes     |
| Phase 8 — Application workspace and packs                   | Kanban/table/calendar, tasks/notes/docs, grounded packs, consistency and outcomes                                                  | Phases 5–7  | Records pin exact resume version; pack claims remain consistent; workflows pass                        |
| Phase 9 — Interview, networking, growth, analytics          | Defense map, STAR stories, interview prep, consent-based CRM, goals/reviews, non-causal analytics                                  | Phases 3, 8 | Stories link claim/evidence; privacy/accessibility tests; analytics language is non-causal             |
| Phase 10 — Commercial, admin, hardening, release            | Entitlements/billing, least-privilege admin, deletion/export/audit, limits, load/security, backup/restore, deployment              | Phases 0–9  | No open critical security issues; idempotent webhooks; deletion and restore tested; full CI/build pass |

Detailed checkboxes live in `docs/implementation-checklist.md`.

## Cross-phase dependency rules

1. Identity and ownership (Phase 1) precede persisted user workflows.
2. The canonical resume model (Phase 2) and evidence graph (Phase 3) precede
   readiness, job matching, generated changes, and exports.
3. Deterministic features and score versions precede any score UI.
4. Job requirement source spans and evidence matches precede Change Studio
   job-specific suggestions.
5. The grounding verifier and immutable versions precede export and application
   pack generation.
6. Exact resume-version linkage precedes outcome analytics.
7. Account deletion/export, audit semantics, and retention rules evolve with each
   data-owning phase; they are not postponed wholesale to launch.

## Assumptions and specification tensions

- The recommended architecture is treated as required unless an ADR documents a
  reason to differ.
- pnpm 11.13.0 and Node 24 govern the JavaScript workspace. Python 3.13 projects
  use uv. Lockfiles, not broad version ranges in this document, are authoritative.
- The API owns Phase 1 sessions and rotating hashed refresh tokens; Google OAuth
  is an adapter. No auth behavior is represented as complete in Phase 0.
- PostgreSQL includes pgvector, but embeddings are introduced only for a measured
  retrieval need. Deterministic rules and relational provenance remain primary.
- Celery uses Redis locally. Production broker durability and topology require a
  later deployment ADR and load/failure testing.
- MinIO is local object storage. Production object storage remains S3-compatible
  and private, with tenant-prefixed randomized keys and short-lived signed URLs.
- “Optional malware scanner service” in local Compose does not make scanning
  optional for production uploads. Phase 2 must fail closed or quarantine when a
  required scanner is unavailable.
- “Current stable dependencies” and reproducibility are reconciled by selecting
  conservative stable compatible releases and tracking exact lockfiles.
- Guest resume health will use an opaque, short-lived capability and strict
  retention; it must not weaken registered-user ownership boundaries.
- The UI image directs hierarchy and visual language only. Its sample names,
  scores, jobs, and claims are not requirements or real data.
- No real AI, OAuth, email, billing, or taxonomy credential is required for Phase
  0; future phases provide environment-selected interfaces and deterministic
  local/fake adapters.

## Risk register

| ID  | Risk                                                              | Likelihood / impact | Mitigation and gate                                                                                                                          | Earliest owner phase   |
| --- | ----------------------------------------------------------------- | ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| R1  | Cross-tenant data exposure through IDOR or object keys            | Medium / Critical   | Ownership-scoped queries, policy tests, private buckets, audit events                                                                        | 1 and every data phase |
| R2  | Malicious or resource-exhausting documents                        | High / Critical     | Signature/limit checks, scanning, isolated no-network worker, time/memory/CPU caps, hostile fixtures                                         | 2                      |
| R3  | AI fabricates or is redirected by document instructions           | High / Critical     | Untrusted-content delimiters, strict schemas, evidence ledger, deterministic grounding, adversarial tests                                    | 5–6                    |
| R4  | Score labels mislead users                                        | Medium / High       | Canonical disclaimer, deterministic versioned formulas, explanations, no probability language                                                | 2, 4, 5                |
| R5  | PDF/DOCX looks correct but parses badly                           | High / High         | Constrained templates, searchable text, round-trip verification and blocking critical failures                                               | 7                      |
| R6  | Dependency/toolchain churn breaks the greenfield baseline         | Medium / Medium     | Conservative pins, lockfiles, CI cache keys, scheduled upgrades in small changes                                                             | 0 onward               |
| R7  | Queue retry duplicates work or cost                               | Medium / High       | Idempotency records, bounded retries/timeouts, job state machine, budgets and dead letters                                                   | 2 onward               |
| R8  | Sensitive content leaks through logs/telemetry/providers          | Medium / Critical   | Data classification, default redaction, payload-free telemetry, provider minimization and consent                                            | 0 onward               |
| R9  | Local Compose health hides production gaps                        | High / High         | Separate readiness, production threat review, load/restore/failure tests, protected deploy                                                   | 10                     |
| R10 | Broad roadmap produces unfinished horizontal scaffolding          | High / Medium       | One vertical phase at a time, dependency gates, no completion on placeholders                                                                | Every phase            |
| R11 | Public Phase 0 demo is mistaken for functional analysis           | Medium / Medium     | Persistent fictional-preview label; no upload/score claims or data persistence                                                               | 0–1                    |
| R12 | Retention/deletion becomes inconsistent across stores             | Medium / High       | Data inventory, deletion tombstones/jobs, object/vector/backup policy and tests per entity                                                   | 1 onward               |
| R13 | Provisional shared schemas drift from implemented OpenAPI         | Medium / High       | Treat only implemented OpenAPI schemas as live; reconcile/remove handwritten error/pagination scaffolding before Phase 1/product collections | 0–1                    |
| R14 | Latest hosted CI run covers the earlier initial commit and failed | Low / Medium        | Run 29349892186 exposed formatting and env-isolation issues now fixed locally; require a green rerun before accepting any Phase 1 merge      | 0–1                    |
| R15 | Newly disclosed upstream runtime findings lack supported patches  | Low / High          | Two exact-version Grype exceptions document reachability and removal conditions; refresh Python/Next base dependencies before Phase 1 merge  | 0–1                    |

## Change and verification protocol

At the end of every phase:

1. Freeze scope and list the changed files.
2. Run formatting, lint, type checks, unit tests, relevant integration tests, and
   end-to-end tests.
3. Capture exact failures; fix them or keep the phase open.
4. Confirm migrations upgrade from the previous revision and have a tested
   rollback/forward-repair story.
5. Update API and product docs, ADRs, threat model, risk register, and this file.
6. Record deferred work and the next phase. Do not use hardcoded UI values to
   simulate missing application state except isolated, labeled demo fixtures.

## Next phase

When work is authorized to continue, begin **Phase 1: Authentication, Application
Shell, and Onboarding**. Start with the identity/session data model, threat-model
review, and cross-user authorization harness before building protected product
pages. Phase 1 is not part of this revision.
