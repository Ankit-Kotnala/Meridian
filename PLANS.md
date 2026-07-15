# CareerOS implementation plan

Last updated: 2026-07-15
Plan owner: engineering  
Current status: **Phase 2 vertical slice implemented and locally verified;
same-revision hosted verification is pending**

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
- [x] pnpm monorepo and one root uv workspace for API, worker, and shared backend
- [x] Thin Next.js routes/feature modules and accessible initial visual system
- [x] FastAPI liveness, dependency readiness, and safe metadata endpoints
- [x] Celery worker and deterministic health task
- [x] PostgreSQL/pgvector, Redis, and MinIO local services
- [x] Shared backend, generated contracts, generic UI/design tokens, strict
      configuration, and fictional test-fixture package boundaries
- [x] Dockerfiles, `compose.yaml`, `.env.example`, and Make command interface
- [x] CI foundation plus architecture, contract-drift, and migration gates
- [x] Cross-service health verification against the aligned working tree

The earlier Phase 0 baseline passed its then-current local gates on 2026-07-14.
The architecture addendum subsequently made a shared Python modular monolith,
single root uv lock, generated OpenAPI schema, thin deployable applications, and
executable dependency boundaries part of Phase 0. That alignment is implemented,
its expanded local gates pass, and commit `9558f33` passed hosted CI run
`29360385761` on 2026-07-15. Phase 0 is complete.

### Architecture-alignment work

- [x] Make `packages/backend` the owner of shared Python foundation code and the
      preserved Alembic revision graph.
- [x] Make API and worker thin members of one root uv workspace and lock; forbid
      backend-to-app, worker-to-API, and deployable persistence imports.
- [x] Generate the committed TypeScript schema from normalized FastAPI OpenAPI,
      expose a typed client wrapper, and fail on export or generation drift.
- [x] Enforce thin web routes, feature-module ownership, and generic UI package
      boundaries.
- [x] Build Python images from the root context, run migrations without uv in the
      runtime image, and verify fresh and existing-database upgrade paths.
- [x] Re-run formatting, lint, type, unit, architecture, contract, migration,
      build, browser, security, and Compose gates in the aligned working tree.
- [x] Commit the aligned tree and obtain a green hosted CI rerun for that exact
      revision.

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
- Browser extension/job capture, empty backend modules or provider integrations,
  root future-test trees, Terraform, and operations artifacts until their owning
  phases

The Phase 0 fictional dashboard remains isolated at `/demo/dashboard`. The real
`/dashboard` is authenticated and intentionally shows an honest empty state until
Phase 2 introduces resume processing and analysis.

### Phase 0 dependencies

```text
Pinned toolchains + root locks + env contract
          |
          +--> packages/backend --> thin API + thin worker
          |           |                    |
          |           +--> Alembic         +--> PostgreSQL/Redis/MinIO readiness
          |
          +--> FastAPI OpenAPI --> generated contracts --> web modules
          |
          +--> architecture checks + Compose health + CI verification
```

The verification gate depends on all branches. Documentation can be reviewed in
parallel but cannot turn a failing runtime gate green.

### Verification commands

The following stable command interface is covered by the aligned local gate and
hosted CI run `29360385761` on committed revision `9558f33`:

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

### Historical Phase 0 baseline evidence

Evidence captured through 2026-07-14 22:20 IST against the pre-alignment working
tree is preserved below. It does not establish that the current working tree
passes.

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

### Aligned Phase 0 local evidence

Local evidence was captured on 2026-07-14 and reconfirmed on 2026-07-15 before
publishing commit `9558f33`. Hosted CI then verified that exact implementation
revision.

| Command / gate                       | Result | Evidence                                                                                                                            |
| ------------------------------------ | ------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/setup.ps1`                  | Pass   | Frozen pnpm and root uv workspace installation completed                                                                            |
| Formatting and lock/contract drift   | Pass   | Prettier and `uv lock --check` passed; normalized OpenAPI remained stable under hostile ambient settings; generated schema matched  |
| JavaScript lint, types, tests, build | Pass   | Turbo graph passed; contracts 3, ESLint config 4, UI 5, and web 4 tests; Next.js built 20 routes                                    |
| Python lint, types, tests            | Pass   | Ruff and mypy passed; backend 16, API 20, and worker 12 tests passed                                                                |
| Containers and migrations            | Pass   | API, worker, and web images built; all six core services became healthy; Alembic upgraded twice and reported `20260714_0001 (head)` |
| Runtime and queue probes             | Pass   | Web/API endpoints returned HTTP 200 and the broker-backed Celery inspect ping returned `pong`                                       |
| Dependency failure/recovery          | Pass   | Readiness returned HTTP 503 with PostgreSQL stopped and HTTP 200 after PostgreSQL recovered                                         |
| Browser checks                       | Pass   | Playwright passed 7 checks with 1 intentional desktop-only skip                                                                     |
| Security gate                        | Pass   | Gitleaks, pnpm audit, and pip-audit passed; Grype's fixable-high gate passed with two documented exact-version exceptions           |
| `scripts/verify.ps1`                 | Pass   | Complete aligned local runtime gate finished with exit code 0                                                                       |
| Hosted CI                            | Pass   | Run 29360385761 passed worker, API, supply-chain, web/contracts, browser-smoke, and container jobs against commit `9558f33`         |

## Phase 1 scope and status

### Included

- [x] Owned user/profile, session, refresh, one-time-token, OAuth, organization,
      membership, consent, audit, and onboarding persistence
- [x] Email registration, verification/resend, login, rotating sessions,
      logout/logout-all, recovery, session revocation, and Google OAuth adapter
- [x] Argon2id password hashing, opaque hashed tokens, replay-family revocation,
      CSRF/origin enforcement, abuse controls, audit events, and owner scoping
- [x] Protected responsive workspace, real empty dashboard, profile/session/
      consent settings, and resumable onboarding with honest Phase 2 handoffs
- [x] Same-origin web API proxy, generated contract bindings, accessible form and
      feedback primitives, and loading/empty/success/error states
- [x] Unit, API, real PostgreSQL/Redis integration, migration round-trip, and
      desktop/mobile primary-workflow E2E coverage

ADR 0008 records the API-owned opaque-session model, same-origin web proxy,
cookie/CSRF policy, refresh rotation, provider boundaries, abuse controls, and
ownership rules. No working Phase 0 behavior was replaced with mock data; the
fictional preview moved to the explicitly labeled demo route.

### Phase 1 local evidence

Evidence was captured on 2026-07-15 from the frozen working tree. Implementation
commit `c4bdbe1` and its evidence commit `baab8f7` preserve the same Phase 1
runtime; hosted run `29367040183` passed all eight checks on `baab8f7`. Phase 1 is
complete.

| Command / gate                       | Result | Evidence                                                                                                                                             |
| ------------------------------------ | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/verify-phase1.ps1`          | Pass   | Consolidated gate completed with exit code 0, including quality, contracts, builds, Compose, migration, integration, and browser checks              |
| Formatting, lint, and strict types   | Pass   | Prettier, Ruff, ESLint/architecture boundaries, strict TypeScript, and mypy passed                                                                   |
| Unit and API tests                   | Pass   | Backend 28, API 34, worker 12, web 17, UI 8, contracts 3, and ESLint-boundary 4 tests passed                                                         |
| Real dependency integration          | Pass   | Two identity workflows passed against isolated PostgreSQL and Redis; the generic unit runner has no hidden integration skips                         |
| Migration `20260715_0002`            | Pass   | Previous revision upgraded to head, downgraded, and re-upgraded; the runtime image migration path reported the expected single head                  |
| Production builds and runtime        | Pass   | API, worker, and web images built; PostgreSQL, Redis, MinIO, Mailpit, API, worker, and web became healthy; Celery returned `pong`                    |
| Primary workflow E2E                 | Pass   | Playwright passed 9 checks on desktop/mobile with 1 intentional desktop-only project exclusion and 0 failures                                        |
| Manual rendered-browser review       | Pass   | Desktop registration, mobile login, the isolated demo, loading state, anonymous redirect, responsive overflow, labels, and visible skip focus passed |
| Contract and body-limit verification | Pass   | Normalized OpenAPI/generated TypeScript stayed in sync; Content-Length and streamed bodies fail safely above the 1 MiB API limit                     |
| Security scan                        | Pass   | Gitleaks, high-level pnpm audit, and pip-audit found no actionable issue; all application images passed Grype's fixable-high gate                    |
| Hosted CI                            | Pass   | Run 29367040183 passed all eight checks, including API, worker, supply-chain, clean web/contracts, browser/auth E2E, and container jobs on `baab8f7` |

The first hosted attempt exposed that local build output had masked a clean-checkout
contracts prerequisite and that a literal fictional E2E password triggered the
external secret scanner. The final tree makes consumer typechecks depend on
dependency builds/typechecks, generates the E2E password per run, removes the
literal from reachable PR history, and passes both gates.

### Explicitly deferred

- Resume upload, malware admission, parsing, canonical resume state, corrections,
  and deterministic Resume Health scoring remain Phase 2 work.
- Live Google credentials are not required for ordinary tests; deterministic
  provider and adapter tests cover OAuth behavior. Production provider selection
  and credentials remain deployment decisions.
- MFA is not presented as implemented. Phase 1 supplies recent-auth and
  future-compatible session hooks only.
- Account export/deletion orchestration, production retention durations, billing,
  administrator tooling, and production deployment remain later-phase work.

## Phase 2 scope and status

Current status: **implemented and locally verified; same-revision hosted
verification is pending**. Items use `[~]` until the hosted gate is recorded.
This section does not supersede a failed or skipped command.

### Implemented vertical slice

- [~] Migration `20260715_0003` adds guest resume sessions, upload intents,
  ownership-scoped source documents and derived artifacts, durable processing
  jobs/outbox and object-cleanup records, immutable canonical snapshots, Resume
  Health analyses, persisted feature values/component contributions/findings,
  per-invocation execution leases, and redacted resume audit events with
  constraints, foreign keys, indexes, and exactly-one-owner checks.
- [~] Account and guest upload-policy/intent/finalize APIs issue short-lived
  signed `PUT`s for randomized staging keys, enforce exact size/media/signature,
  rate/quota/scope, and promote accepted bytes into private randomized
  quarantine keys without returning permanent credentials or a standalone/
  unsigned object-key field. The staging key is exposed only inside its
  short-lived, operation-scoped signed URL.
- [~] Required ClamAV and guarded local PDF/DOCX extraction run in the restricted
  worker. Wrong-signature, malformed/encrypted/polyglot, macro, traversal,
  expansion, PDF-page/universal-character-limit, timeout, malware, and
  scanner-unavailable cases fail safely. Image-only input is identified; no OCR
  adapter is enabled.
- [~] Parse, analyze, and delete use durable owner-scoped jobs with idempotency,
  progress, bounded retry/dead letter, safe errors, trace IDs,
  an allowlisted queue envelope, a per-invocation fencing token, and an execution
  lease longer than the worker hard timeout. A concurrent delivery receives a
  delayed busy retry; an expired lease can be recovered without allowing its
  stale predecessor to commit. Transactional outbox publication and object
  cleanup both use bounded batches, durable attempts, backoff, and terminal
  dead-letter state. Scheduled dispatch and retention maintenance use the same
  worker application services. A scheduled database-only reconciler detects
  stale published queue work, retryable failures with lost retries, and expired
  running leases; it fences, republishes, or dead-letters them within separate
  processing and recovery attempt budgets. Parse/analyze jobs support cooperative
  cancellation; an accepted delete job is intentionally noncancellable.
- [~] Extraction persists plain-text and reading-order artifacts plus canonical
  sections/blocks with confidence and source spans. User correction requires
  optimistic concurrency and creates an immutable successor snapshot without
  changing the extracted source. Correction and analysis have separate
  ownership-scoped rate classes; correction rejects an all-no-op request and the
  domain caps canonical revisions and analysis history per document.
- [~] Resume Health engine `resume-health/1.0.0` with configuration
  `resume-health-default/1` uses the exact published fixed-point feature and
  component formula. Each immutable analysis persists feature schema
  `resume-health-features/1`, the complete typed feature values, each component's
  weighted feature contributions, and a feature hash; it exposes deterministic
  findings/explanations and returns insufficient data rather than a deceptive
  zero.
- [~] The account and short-retention guest web workflows implement direct upload
  progress/abort, processing polling/cancel, document list/empty state,
  plain-text and reading-order review, source-preserving correction, analysis,
  report, explicit consented claim, and durable deletion with loading, empty,
  success, and safe error states.
- [~] Reports carry the canonical internal-measure disclaimer, real component and
  finding data, and keyboard/mobile/color-independent accessible summaries.
  Keyboard-operable disclosure panels expose the stored feature values and exact
  score/weight/contribution trace rather than relying on color or a chart. No
  working Phase 1 functionality is replaced with fixture or mock data.

### Architecture decisions realized

- FastAPI remains the OpenAPI authority and thin authorization/validation adapter;
  generated contracts are consumed by the Next.js feature module.
- `packages/backend/src/careeros/modules/resume_health` owns framework-free domain
  rules and application ports/use cases. SQLAlchemy, S3, ClamAV, and Celery
  adapters point inward; the worker does not import the API.
- Direct object transfer is split into staging and quarantine. A signed URL grants
  one key/method/header/TTL-scoped upload operation, never resource ownership;
  finalize and every worker action recheck durable scope/state.
- The Compose `web-edge` discards client-selected forwarding headers, derives the
  source from its socket peer, and is the only host-published web listener. The
  otherwise unexposed web BFF converts that neutral address into an opaque HMAC-
  signed source signal; the API verifies it before using it for pre-authentication
  and first-guest upload abuse controls. The signal is rate-key input, never
  identity or resource authorization.
- HTTP observability records only route templates, status/duration, request/trace
  context, and exception class. Raw paths/queries, bodies, headers, exception
  messages, signed URLs, document text, and provider payloads are excluded, and
  payload-bearing library access logs are disabled. An unexpected HTTP exception
  becomes a generic no-store `internal_error` response at this boundary instead
  of being re-raised into the server logger.
- Job creation and queue intent share a database transaction. The bounded,
  retrying outbox publisher closes the database/broker consistency gap without
  enqueuing raw document bytes or credentials. Promotion/claim compensation and
  orphaned staging/quarantine cleanup use durable cleanup rows; explicit document
  deletion is itself a fenced durable job and adds a staging backstop. Transient
  object-store failures are retried and eventually visible as job or cleanup
  dead-letter state rather than silently abandoned.
- Guest access is an opaque high-entropy capability stored as a keyed hash and
  delivered in an `HttpOnly` path-scoped cookie. A separate guest CSRF token and
  exact-origin policy protect mutation. One active guest intake defaults to
  24-hour retention; explicit account claim requires a ready document, completed
  analysis, no active/retryable job, consent, and account quota. It rekeys
  objects, transfers retained content/job history, and only then revokes the
  guest capability. Prior guest audit records retain their original scope.
- Canonical correction and score analysis are append-only. Analyses reference one
  immutable snapshot and one immutable formula/configuration/feature-schema
  version. Resume mutation headers are bounded consistently: `Idempotency-Key`
  is 8-128 characters from `[A-Za-z0-9._:-]`, and `If-Match` is a quoted positive
  PostgreSQL `int4` value no greater than 2147483647.

### Migration and compatibility

`20260715_0003` depends on the verified Phase 1 head `20260715_0002`. It is
additive and does not rename or remove Phase 1 tables or routes. Its downgrade
removes Phase 2 data in reverse foreign-key order; production rollback after real
uploads would therefore require data retention/export review rather than an
automatic destructive downgrade. The required test path is previous head -> new
head -> previous head -> new head plus a fresh bootstrap and single-head check.

### Local verification evidence

Evidence was captured on 2026-07-15 from the frozen Phase 2 working tree. The
implementation remains open only for the required same-revision hosted CI gate.

| Command / gate                                     | Status  | Evidence                                                                                                                                                                                                                                                |
| -------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frozen installs and lock checks                    | Pass    | Frozen pnpm and root uv workspace installs completed; `uv lock --check` and fixture manifest size/SHA-256 verification passed                                                                                                                           |
| Formatting and lint                                | Pass    | Prettier, Ruff format/check, ESLint, and executable dependency-boundary checks passed                                                                                                                                                                   |
| Strict type checking                               | Pass    | TypeScript and mypy passed for the web/contracts/UI and all Python packages                                                                                                                                                                             |
| Unit and API tests                                 | Pass    | 280 tests passed: backend 88, API 67, worker 54, web 50, UI 12, contracts 3, boundary 4, and edge 2; the generic backend run's 5 explicit provider-environment skips were exercised separately below                                                    |
| Contract drift and production builds               | Pass    | Normalized OpenAPI/generated TypeScript remained clean; Next.js built 31 routes/pages and all application images built                                                                                                                                  |
| Migration and real integration                     | Pass    | Fresh bootstrap and `20260715_0002 -> 20260715_0003 -> 20260715_0002 -> 20260715_0003` passed; 5 real PostgreSQL/Redis/MinIO/ClamAV/provider integrations passed                                                                                        |
| Primary E2E                                        | Pass    | Playwright passed 10 checks with 2 intentional project exclusions and 0 failures across registered/guest desktop/mobile workflows                                                                                                                       |
| Accessibility and rendered review                  | Pass    | Automated semantics plus manual keyboard/rendered review covered desktop/mobile upload, selection, processing, structured/plain review, and report; labels, skip focus, tabs, disclosures, disclaimer, controls, and overflow passed; no console errors |
| Runtime and dependency recovery                    | Pass    | Hardened Compose policy, worker and Beat scheduler health, anonymous MinIO denial, packaged readiness HTTP 503 while PostgreSQL was stopped, recovery to HTTP 200, and isolated cleanup passed                                                          |
| Security scan                                      | Pass    | Separate Gitleaks and Node audits passed; pip-audit found no known vulnerability after `pypdf` 6.13.3; API, worker, web, and `web-edge` passed the Grype fixable-high gate subject to documented reachability exceptions                                |
| `scripts/verify-phase2.ps1` / `make verify-phase2` | Pass    | Consolidated frozen-tree gate exited 0, including migration, integration, runtime, browser, build, and cleanup checks                                                                                                                                   |
| Hosted CI                                          | Pending | all required jobs must pass on the exact Phase 2 evidence revision                                                                                                                                                                                      |

### Known limitations and deferred work

- OCR is an explicit port but no provider is enabled; image-only PDFs produce a
  parser warning and insufficient-data report rather than invented text.
- The committed benign corpus covers deterministic one-column PDF, DOCX, and
  image-only PDF. Additional two-column, header/footer, table-heavy, locale,
  unusual-font, bidirectional-Unicode, and long-document fixtures remain ongoing
  parser-compatibility work, not claimed Phase 2 coverage.
- PDF has an authoritative extractor page-count cap. The local `python-docx`
  path cannot reliably infer rendered DOCX pages, so DOCX is instead bounded by
  upload bytes, archive entries, expanded bytes/ratio, extracted characters/
  blocks, and artifact size. Layout-aware DOCX page enforcement requires a later
  rendering provider.
- Resume Health is job-independent document analysis. It does not create the
  career-profile/evidence source of truth, verify a claim, measure role/job fit,
  call an AI provider, or predict hiring outcomes.
- Explicit document deletion covers Phase 2 objects and relational content.
  Account-wide export/erasure, backups, legal retention, production lifecycle,
  support access, managed storage/scanner/queue selection, and restore exercises
  remain Phase 10 release work.
- Local Compose hardening and ClamAV prove the development contract, not an
  internet-facing production sandbox or zero-day immunity.
- The local extractor runs blocking parser code through `asyncio.to_thread`.
  Its application timeout cancels the await but cannot forcibly stop that Python
  thread. Celery task limits plus the non-root, read-only, CPU/memory/PID-bounded,
  no-edge-network worker reduce impact; a killable per-parser subprocess remains
  security hardening work before production exposure.
- Upload retry state is intentionally held only in the mounted browser component.
  An ambiguous transfer/finalize failure can reuse the same intent and finalize
  key while that page remains mounted, but a lost upload-intent response or page
  reload can consume quota until the default five-minute intent TTL expires.
  Phase 2 does not provide chunked or resumable file transfer.
- The local `web-edge` trusts only its direct socket peer and overwrites every
  client-selected address header. A cloud load balancer would therefore collapse
  source attribution to the balancer address until a deployment-specific,
  allowlisted trusted-hop policy is added; production deployment must not simply
  start trusting arbitrary forwarding headers.

## Roadmap and phase gates

| Phase                                                       | Outcomes                                                                                                                           | Depends on  | Exit evidence                                                                                          |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------ |
| Phase 0 — Foundation                                        | Root workspaces, shared backend, thin deployables, generated contracts, local dependencies, health, CI, docs                       | None        | Architecture/contracts/migrations pass; setup/dev healthy; format, lint, types, tests pass             |
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
- pnpm 11.13.0 and Node 24 govern the JavaScript workspace. Python 3.13 API,
  worker, and backend packages use one root uv workspace and lock. Lockfiles, not
  broad version ranges in this document, are authoritative.
- The API owns Phase 1 sessions and rotating hashed refresh tokens; Google OAuth
  is an adapter. No auth behavior is represented as complete in Phase 0.
- PostgreSQL includes pgvector, but embeddings are introduced only for a measured
  retrieval need. Deterministic rules and relational provenance remain primary.
- Celery uses Redis locally. Production broker durability and topology require a
  later deployment ADR and load/failure testing.
- MinIO is local object storage. Production object storage remains S3-compatible
  and private, with tenant-prefixed randomized keys and short-lived signed URLs.
- ClamAV is required by the Phase 2 local stack. The processor fails closed and
  retains quarantine during bounded retry when the scanner is unavailable.
  Production scanner/service selection still requires deployment review.
- “Current stable dependencies” and reproducibility are reconciled by selecting
  conservative stable compatible releases and tracking exact lockfiles.
- Guest Resume Health uses a keyed-hash opaque, short-lived capability, separate
  CSRF/origin checks, one active intake, and strict retention without weakening
  registered-user ownership boundaries.
- The UI image directs hierarchy and visual language only. Its sample names,
  scores, jobs, and claims are not requirements or real data.
- Mailpit exercises real local SMTP delivery without external email credentials.
  Google OAuth is disabled unless its complete provider configuration is supplied,
  and deterministic adapters cover ordinary tests. AI, billing, taxonomy, and
  production provider credentials remain later-phase/deployment decisions.

## Risk register

| ID  | Risk                                                             | Likelihood / impact | Mitigation and gate                                                                                                                                                                                              | Earliest owner phase   |
| --- | ---------------------------------------------------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| R1  | Cross-tenant data exposure through IDOR or object keys           | Medium / Critical   | Ownership-scoped queries, policy tests, private buckets, audit events                                                                                                                                            | 1 and every data phase |
| R2  | Malicious or resource-exhausting documents                       | High / Critical     | Signature/limit checks, scanning, isolated no-network worker, time/memory/CPU caps, hostile fixtures                                                                                                             | 2                      |
| R3  | AI fabricates or is redirected by document instructions          | High / Critical     | Untrusted-content delimiters, strict schemas, evidence ledger, deterministic grounding, adversarial tests                                                                                                        | 5–6                    |
| R4  | Score labels mislead users                                       | Medium / High       | Canonical disclaimer, deterministic versioned formulas, explanations, no probability language                                                                                                                    | 2, 4, 5                |
| R5  | PDF/DOCX looks correct but parses badly                          | High / High         | Constrained templates, searchable text, round-trip verification and blocking critical failures                                                                                                                   | 7                      |
| R6  | Dependency/toolchain churn breaks the greenfield baseline        | Medium / Medium     | Conservative pins, lockfiles, CI cache keys, scheduled upgrades in small changes                                                                                                                                 | 0 onward               |
| R7  | Queue retry duplicates work or cost                              | Medium / High       | Idempotency records, bounded retries/timeouts, job state machine, budgets and dead letters                                                                                                                       | 2 onward               |
| R8  | Sensitive content leaks through logs/telemetry/providers         | Medium / Critical   | Data classification, default redaction, payload-free telemetry, provider minimization and consent                                                                                                                | 0 onward               |
| R9  | Local Compose health hides production gaps                       | High / High         | Separate readiness, production threat review, load/restore/failure tests, protected deploy                                                                                                                       | 10                     |
| R10 | Broad roadmap produces unfinished horizontal scaffolding         | High / Medium       | One vertical phase at a time, dependency gates, no completion on placeholders                                                                                                                                    | Every phase            |
| R11 | Public demo is mistaken for functional analysis                  | Medium / Medium     | Isolate it at `/demo/dashboard`, retain the fictional-preview label, and keep it free of upload/score claims or account persistence                                                                              | 0–1                    |
| R12 | Retention/deletion becomes inconsistent across stores            | Medium / High       | Data inventory, deletion tombstones/jobs, object/vector/backup policy and tests per entity                                                                                                                       | 1 onward               |
| R13 | Generated contracts drift from implemented OpenAPI               | Medium / High       | FastAPI remains authoritative; pin normalized export/client generation and fail CI on either drift                                                                                                               | 0 onward               |
| R14 | Hosted CI and local behavior diverge after architecture changes  | Low / Medium        | Runs 29360385761 and 29367040183 verify foundation and Phase 1; Phase 2 local gates pass and its hosted evidence is pending; retain clean contract-output, container, migration, browser, and supply-chain gates | 0 onward               |
| R15 | Upstream runtime findings do not all have supported stable fixes | Low / High          | Two exact-version Grype exceptions document reachability and removal conditions; monitor remaining findings and refresh runtimes promptly                                                                        | 0–1                    |
| R16 | Workspace/migration move regresses runtime or existing databases | Medium / High       | One root lock, preserved revision IDs, fresh/existing upgrade tests, root-context image builds, and direct runtime Alembic verification                                                                          | 0                      |

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

The Phase 2 implementation and local verification gate passed. Phase closeout and
Phase 3 remain blocked until this evidence tree is committed and every required
hosted CI job passes that exact revision.

After Phase 2 is verified, the next phase is **Phase 3 — Career Profile, Evidence
Vault, and Achievement Inbox**. It begins with independent owned career entities
and a provenance/evidence graph. Resume import and corrections may propose
profile changes, but they cannot overwrite career truth. Every factual claim and
number must retain eligible evidence, explicit state, conflict handling, owner
scope, audit history, and a user confirmation path before downstream readiness,
matching, or generation can consume it.
