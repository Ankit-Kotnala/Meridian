# Rezumi implementation plan

Last updated: 2026-07-27
Plan owner: engineering  
Current status: **Phase 1/3 observed-onboarding, Settings, and resume-ready Career
Record closure is locally verified; hosted evidence is pending explicit
authorization to publish. Phase 2 semantic parsing/review closure is also
locally/security verified with hosted evidence pending. Phase 9 remains complete
and hosted verified in PR #22; Phase 8 remains complete and hosted verified in
PR #21. Phase 7 durable verified-export closure and Phase 10A's guarded fictional
local seed are merged. The product-wide UX redesign is locally implemented and
visually verified without changing backend phase completion. Commercial,
tenancy, privacy, administration, security/cost, infrastructure, and final
release-hardening work remains open**

## Status legend

- `[ ]` not started
- `[~]` in progress or implemented but not yet verified
- `[x]` implemented and verified in the current working tree
- `[!]` blocked; the blocker and evidence must be recorded

No phase is complete until every exit gate passes. A skipped check is not a pass.

## Product-wide UX redesign verification (2026-07-27)

This cross-cutting redesign is isolated on `agent/enterprise-ui-redesign`. It changes the
presentation and workflow clarity of existing product functionality; it does not
claim a new implementation phase, publish a deployment, or change backend domain
rules.

### Implemented and verified

- [x] Replaced the decorative dashboard direction with a warm-neutral,
      forest-action, evidence-first token and component system.
- [x] Added shared page, section, stepper, definition-list, approval, and state
      patterns while keeping product behavior in feature modules.
- [x] Reorganized authenticated navigation by user goal and implemented a
      keyboard-operable mobile drawer and contextual account controls.
- [x] Rebuilt public, identity, dashboard, onboarding, Career Record,
      opportunity, resume, application, preparation, networking, growth,
      analytics, and Settings top-level experiences without invented metrics,
      claims, customer evidence, or capabilities.
- [x] Rebuilt the public home page as the first page-level enterprise pass:
      a credible fictional workspace preview, platform-layer architecture,
      controlled operating workflow, explicit trust controls, and restrained
      technical-preview messaging replaced the flat documentation-style
      presentation. The focused rerun passed at all seven required widths with
      zero CLS, no overflow, and no browser or console error.
- [x] Added a bounded enterprise interaction layer: pinned Motion with
      `LazyMotion`, central OS reduced-motion handling, route-scoped landing and
      workspace providers, CSS-only public navigation motion, subtle ambient
      depth, and measured bundle impact.
- [x] Documented design foundations, component ownership, provenance and
      approval patterns, responsive rules, accessibility expectations, and
      current official product-pattern research in
      `docs/product-design-system.md`.
- [x] Added `apps/web/scripts/capture-visual-qa.mjs` and the complete route/state
      record in `docs/visual-qa-matrix.md`.
- [x] Captured four representative public workflows at all seven required
      viewports. The 28 committed redesigned captures returned 200 with no page
      overflow, console error, or page error; skip-link and reduced-motion checks
      passed.
- [x] Exercised 24 authenticated top-level routes at 320, 360, 393, 768, 1024,
      1440, and 1920 px. One Applications filter overflow at 1440 px was fixed,
      rebuilt, and rerun successfully at all seven widths.
- [x] Verified the production Next.js image behind the local edge container with
      all Compose services healthy. The authenticated desktop/mobile journey
      passes 2/2 and the production-stack smoke suite passes 7 with 1 intentional
      project skip.

### Required gate evidence

- `pnpm format:check`: pass.
- `pnpm lint`: pass.
- `pnpm typecheck`: pass.
- `pnpm test`: pass — web 163, UI 12, contracts 3, boundary 4, and edge 2 tests.
- Exact Makefile Python format/lint commands: pass.
- Exact Makefile Python mypy commands: pass — 208 backend, 65 API, and 12 worker
  source files.
- Exact Makefile Python test commands: pass — 398 backend architecture/unit,
  145 API, and 84 worker tests.
- `pnpm build`: pass; 49 routes compiled. The final Docker image build also
  compiled all 49 routes and the stack reached healthy status.
- `uv lock --check` and `pnpm contracts:check`: pass.
- `docker compose config --quiet`: pass.
- GNU Make is unavailable on this Windows host, so `make format-check`,
  `make lint`, `make typecheck`, and `make test` cannot be invoked by name. Their
  underlying package-manager commands were run directly; this limitation is not
  recorded as a Make pass.

### Interaction-polish incremental gate (2026-07-26)

- `pnpm format:check`: pass.
- `pnpm lint`: pass, including web architecture and repository boundaries.
- `pnpm typecheck`: pass across all JavaScript/TypeScript packages.
- `pnpm test`: pass — web 163, UI 12, contracts 3, boundary 4, and edge 2 tests.
- `pnpm build`: pass; all 49 Next.js routes compiled in the repository build.
- Isolated development-server visual QA: 28/28 public captures passed across the
  seven required widths with zero overflow, console error, or page error.
- Optimized-build visual QA: 21/21 landing, fictional-demo, and login captures
  passed across the seven widths. Maximum observed LCP was 1008 ms, CLS was 0,
  maximum Event Timing duration was 40 ms, and maximum encoded JavaScript was
  236,893 bytes.
- Representative human review completed for the current landing desktop/mobile
  and protected Applications mobile captures through a sandbox-safe encoded
  preview path.

### Completion and publication gate (2026-07-27)

- `pnpm format:check`, `pnpm lint`, and `pnpm typecheck`: pass, including strict
  frontend architecture and repository-boundary enforcement.
- `pnpm test`: pass — web 163, UI 12, contracts 3, boundary 4, and edge 2 tests.
- `pnpm build`: pass; the production Next.js build compiled all 49 routes.
- Production-mode public visual QA: 28/28 captures passed across four routes and
  all seven required widths with zero overflow, console error, page error,
  reduced-motion failure, or lab-threshold regression. Maximum observed LCP was
  512 ms, CLS was 0, maximum interaction duration was 88 ms, and maximum encoded
  JavaScript was 246,612 bytes.
- Production-mode protected visual QA: 168/168 captures passed across 24 routes
  and all seven required widths with zero overflow, console error, page error,
  reduced-motion failure, or lab-threshold regression. Maximum observed LCP was
  472 ms, CLS was 0, maximum interaction duration was 40 ms, and maximum encoded
  JavaScript was 446,839 bytes.
- The stale pre-redesign landing and mobile-navigation smoke assertions were
  corrected to the shipped product language. The serial desktop/mobile Chromium
  rerun passed 7 tests with 1 intentional desktop skip. The initial six-worker
  attempt is retained as host-resource failure evidence; Chromium workers exited
  before assertions completed.
- `docker compose ps`: the API, web, edge, PostgreSQL, Redis, MinIO, Mailpit,
  ClamAV, worker, and scheduler services were healthy during protected QA.

### Workspace home revamp (2026-08-16)

The authenticated `/dashboard` was rebuilt from a prose walkthrough into a
data-backed workspace home. `apps/web/src/modules/workspace/server/dashboard-summary.ts`
reads only the signed-in account's own read-only endpoints (achievements,
applications, evidence, experiences, due networking reminders, skills) in
parallel; each section degrades to an explicit "unavailable" state instead of an
invented zero, and a full cursor page renders as `100+` rather than an exact
total the API does not promise. No metric is hardcoded and the canonical internal
-score disclaimer remains on the resume-state and operating-model sections.

- [x] Masthead with the greeting and the next-best-step decision, career-record
      stat tiles, an account-derived review queue, a stage-grouped application
      pipeline with a screen-reader text summary, the persisted resume state,
      quick launch, and the truth-lock note.
- [x] Route-matched loading skeleton and workspace-width error state.
- [x] `pnpm format:check`, `pnpm lint` (including web architecture and repository
      boundaries), and `pnpm typecheck`: pass.
- [x] `pnpm test`: pass — 45 web files/176 tests plus UI, contracts, boundary, and
      edge suites. 13 of those web tests cover the new summary aggregator and
      dashboard states.
- [!] `make test-e2e`, `make test-integration`, `pnpm build`, and the Python gates
  were not run: the Docker daemon is unavailable on this host and no Python
  surface changed. Visual verification used a static server render of the new
  view against the compiled Tailwind stylesheet at 1440 px and 420 px in light
  and dark themes, not the running stack.

### Open verification and product risks

- [!] The connected interactive browser and direct local-image tool remain
  blocked by the Windows sandbox helper error `apply deny-read ACLs`.
  Playwright completed the repeatable checks, and representative captures were
  manually inspected through a sandbox-safe encoded preview; exhaustive human
  review of every saved screenshot is not claimed.
- [!] Dynamic detail routes require stable domain records. Their component and
  journey coverage is recorded separately from the seven-viewport top-level
  route pass.
- [!] The corrected full-stack E2E suite still receives the existing API `409
resume_builder_conflict` response when newly registered users create a
  resume after evidence confirmation. Resume Builder and downstream
  Application journeys therefore remain open outside this presentation-only
  redesign.
- [!] The Job Match full-stack assertion expects a tailoring action even when
  the deterministic result contains a mandatory gap. The honest UI result is
  retained and the stale expectation remains open.
- [!] No field RUM was available. LCP, CLS, JavaScript bytes, and Event Timing in
  the visual-QA record are local lab observations, not production Core Web
  Vitals or a hiring-outcome claim.

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
`/dashboard` is authenticated and summarizes only the signed-in account's own
persisted records; it shows honest empty and unavailable states rather than
placeholder metrics.

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
docker compose exec worker python -m rezumi_worker.healthcheck
make format-check
make lint
make typecheck
make test
make verify
```

The worker health command uses Celery remote control through the broker and checks
that the running worker can respond; the registered deterministic task is
`rezumi.worker.health.ping`.

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

Current status: **the authentication, session, and application-shell slice is
complete and hosted verified; server-observed onboarding and Settings closure is
locally verified with hosted closure evidence pending authorization**. The
historical gate remains valid for the shipped slice. The current closure adds the
pipeline-aware onboarding state machine and complete Phase 1 account/profile/
preference/security Settings surface while leaving actual account export,
deletion, billing, and scheduled delivery to their owning release workflows.

### Included

- [x] Owned user/profile, session, refresh, one-time-token, OAuth, organization,
      membership, consent, audit, and onboarding persistence
- [x] Email registration, verification/resend, login, rotating sessions,
      logout/logout-all, recovery, session revocation, and Google OAuth adapter
- [x] Argon2id password hashing, opaque hashed tokens, replay-family revocation,
      CSRF/origin enforcement, abuse controls, audit events, and owner scoping
- [x] Protected responsive workspace and real empty dashboard plus profile,
      session, consent, security, notification-preference, privacy, connection,
      and billing-capability Settings use real server state and honest
      unavailable states.
- [x] Onboarding stores intent and explicit skips while upload, processing,
      typed-review, and analysis progress come from an owner-scoped Resume Health
      application query. The browser cannot submit those observations.
- [x] Recent-auth password change verifies the current credential when present,
      invalidates reset tokens, and revokes every session. OAuth-only accounts
      may set a first password; Google removal is blocked when no other login
      method remains; security activity is owner-scoped and redacted.
- [x] Same-origin web API proxy, generated contract bindings, accessible form and
      feedback primitives, and loading/empty/success/error states
- [x] Unit, API, real PostgreSQL/Redis integration, migration round-trip, and
      desktop/mobile primary-workflow E2E coverage

ADR 0008 records the API-owned opaque-session model, same-origin web proxy,
cookie/CSRF policy, refresh rotation, provider boundaries, abuse controls, and
ownership rules. No working Phase 0 behavior was replaced with mock data; the
fictional preview moved to the explicitly labeled demo route.
ADR 0017 records the additive observed-onboarding query and fail-closed Settings
capability boundary. Export, account deletion, billing, and scheduled
notification delivery report unavailable until complete workflows exist.

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

### Phase 1 closure evidence — 2026-07-26

| Command / gate                         | Result           | Evidence                                                                                                                                                                                                                                                                                                                                                                               |
| -------------------------------------- | ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Focused identity and API suites        | Pass             | 22 backend/API tests cover observed onboarding, password rotation, session invalidation, Settings capabilities, security activity, and Google disconnect behavior.                                                                                                                                                                                                                     |
| Real PostgreSQL identity repository    | Pass             | Password rotation revokes the session and owner-scoped audit activity excludes another user's records.                                                                                                                                                                                                                                                                                 |
| Settings component suite               | Pass             | 3 web tests cover the session surface plus account-security and unavailable-capability states.                                                                                                                                                                                                                                                                                         |
| Generated contracts                    | Pass             | `pnpm contracts:generate` updated the normalized OpenAPI artifact and generated TypeScript schema from FastAPI. `pnpm contracts:check`, contracts build, and the unchanged web typecheck pass; additive response defaults preserve existing client fixtures.                                                                                                                           |
| Documented `make format-check`         | Tool unavailable | PowerShell could not resolve `make`. The underlying pinned Prettier/Ruff commands are run directly; this host-tool failure is not reported as a pass.                                                                                                                                                                                                                                  |
| Cumulative `scripts/verify-phase3.ps1` | Pass             | The current-tree cumulative gate passed in 336.3 seconds. It includes all Phase 1 format/lint/type/unit/API/build/Compose checks plus desktop/mobile authentication, honest onboarding, Settings/session control, and latest-head migration coverage. The narrower Phase 1 wrapper also now explicitly selects Phase 1 and preserves the historical `20260714_0001` rollback boundary. |

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

Current status: **the secure intake, extraction, typed semantic parsing/review,
and Resume Health v2 implementation is complete and locally/security verified.
Hosted closure evidence remains pending explicit authorization to publish**.
Historical implementation commit `3b8d639` and hosted CI run `29378312134`
remain evidence for the original generic-block v1 slice only.

### Implemented vertical slice

- [x] Migration `20260715_0003` adds guest resume sessions, upload intents,
      ownership-scoped source documents and derived artifacts, durable processing
      jobs/outbox and object-cleanup records, immutable canonical snapshots, Resume
      Health analyses, persisted feature values/component contributions/findings,
      per-invocation execution leases, and redacted resume audit events with
      constraints, foreign keys, indexes, and exactly-one-owner checks.
- [x] Account and guest upload-policy/intent/finalize APIs issue short-lived
      signed `PUT`s for randomized staging keys, enforce exact size/media/signature,
      rate/quota/scope, and promote accepted bytes into private randomized
      quarantine keys without returning permanent credentials or a standalone/
      unsigned object-key field. The staging key is exposed only inside its
      short-lived, operation-scoped signed URL.
- [x] Required ClamAV and guarded local PDF/DOCX extraction run in the restricted
      worker. Wrong-signature, malformed/encrypted/polyglot, macro, traversal,
      expansion, PDF-page/universal-character-limit, timeout, malware, and
      scanner-unavailable cases fail safely. Image-only input is identified; no OCR
      adapter is enabled.
- [x] Parse, analyze, and delete use durable owner-scoped jobs with idempotency,
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
- [x] Extraction persists plain-text and reading-order artifacts plus canonical
      sections/blocks with confidence and source spans. User correction requires
      optimistic concurrency and creates an immutable successor snapshot without
      changing the extracted source. Correction and analysis have separate
      ownership-scoped rate classes; correction rejects an all-no-op request and the
      domain caps canonical revisions and analysis history per document.
- [x] A typed semantic sidecar models contact, experience, education, project,
      skill, and certification entities; closed field types; stable IDs; exact
      source anchors; date precision; confidence; and explicit field/entity review
      state. Typed confirm/correct/add/remove/reclassify operations require
      ownership and optimistic concurrency and create immutable successor
      snapshots. Corrections retain source provenance, while user-added facts are
      explicitly unanchored rather than falsely attributed.
- [x] Resume Health engine `resume-health/2.0.0` with configuration
      `resume-health-default/2` uses the documented fixed-point semantic coverage,
      review, date-precision, breadth, and existing layout/content feature formula.
      Each immutable analysis persists `resume-health-features/2`, typed feature
      values, weighted contributions, and a feature hash; historical v1 analysis
      records remain strictly readable. Sparse/image-only input still returns
      insufficient data rather than a deceptive zero.
- [x] The account and short-retention guest web workflows implement direct upload
      progress/abort, processing polling/cancel, document list/empty state,
      plain-text, reading-order, and typed semantic review; per-fact
      confirm/correct/remove; entity reclassification/removal; user-supported
      additions; explicit no-change confirmation; legacy snapshot upgrade;
      analysis; report; explicit consented claim; and durable deletion with
      loading, empty, success, and safe error states.
- [x] Reports carry the canonical internal-measure disclaimer, real component and
      finding data, and keyboard/mobile/color-independent accessible summaries.
      Keyboard-operable disclosure panels expose the stored feature values and exact
      score/weight/contribution trace rather than relying on color or a chart. No
      working Phase 1 functionality is replaced with fixture or mock data.

### Architecture decisions realized

- FastAPI remains the OpenAPI authority and thin authorization/validation adapter;
  generated contracts are consumed by the Next.js feature module.
- `packages/backend/src/rezumi/modules/resume_health` owns framework-free domain
  rules and application ports/use cases. SQLAlchemy, S3, ClamAV, and Celery
  adapters point inward; the worker does not import the API.
- Document text extraction, layout analysis, semantic parsing, OCR, and malware
  scanning are independent inward-facing ports with deterministic local adapters.
  Hostile document parsing executes in a dedicated child process with bounded
  input/output, resource limits, no inherited standard streams, timeout
  termination followed by child reaping, and guaranteed temporary-workspace
  cleanup.
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

Evidence was captured on 2026-07-15 from the frozen Phase 2 working tree.
Implementation commit `3b8d639` passed hosted CI run `29378312134` after the
complete local gate below.

| Command / gate                                     | Status | Evidence                                                                                                                                                                                                                                                |
| -------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frozen installs and lock checks                    | Pass   | Frozen pnpm and root uv workspace installs completed; `uv lock --check` and fixture manifest size/SHA-256 verification passed                                                                                                                           |
| Formatting and lint                                | Pass   | Prettier, Ruff format/check, ESLint, and executable dependency-boundary checks passed                                                                                                                                                                   |
| Strict type checking                               | Pass   | TypeScript and mypy passed for the web/contracts/UI and all Python packages                                                                                                                                                                             |
| Unit and API tests                                 | Pass   | 280 tests passed: backend 88, API 67, worker 54, web 50, UI 12, contracts 3, boundary 4, and edge 2; the generic backend run's 5 explicit provider-environment skips were exercised separately below                                                    |
| Contract drift and production builds               | Pass   | Normalized OpenAPI/generated TypeScript remained clean; Next.js built 31 routes/pages and all application images built                                                                                                                                  |
| Migration and real integration                     | Pass   | Fresh bootstrap and `20260715_0002 -> 20260715_0003 -> 20260715_0002 -> 20260715_0003` passed; 5 real PostgreSQL/Redis/MinIO/ClamAV/provider integrations passed                                                                                        |
| Primary E2E                                        | Pass   | Playwright passed 10 checks with 2 intentional project exclusions and 0 failures across registered/guest desktop/mobile workflows                                                                                                                       |
| Accessibility and rendered review                  | Pass   | Automated semantics plus manual keyboard/rendered review covered desktop/mobile upload, selection, processing, structured/plain review, and report; labels, skip focus, tabs, disclosures, disclaimer, controls, and overflow passed; no console errors |
| Runtime and dependency recovery                    | Pass   | Hardened Compose policy, worker and Beat scheduler health, anonymous MinIO denial, packaged readiness HTTP 503 while PostgreSQL was stopped, recovery to HTTP 200, and isolated cleanup passed                                                          |
| Security scan                                      | Pass   | Separate Gitleaks and Node audits passed; pip-audit found no known vulnerability after `pypdf` 6.13.3; API, worker, web, and `web-edge` passed the Grype fixable-high gate subject to documented reachability exceptions                                |
| `scripts/verify-phase2.ps1` / `make verify-phase2` | Pass   | Consolidated frozen-tree gate exited 0 in 199.8 seconds after hosted-failure repair, including migration, integration, runtime, browser, build, and cleanup checks                                                                                      |
| Hosted CI                                          | Pass   | Run `29378312134` passed API, worker, web/contracts, supply-chain, browser-smoke, Resume Health E2E, and container/image jobs on implementation commit `3b8d639`; GitGuardian also passed                                                               |

The first hosted attempt, run `29377566406`, showed that local Docker Compose
5.1.1 tolerated a healthcheck-disabled Beat service while hosted Compose 2.38.2
rejected it under `--wait`. The scheduler now has a PID/process-specific
health probe, both E2E runners assert it explicitly, failure paths retain bounded
diagnostics before cleanup, and the repaired local and hosted gates pass.

### Typed semantic closure verification — 2026-07-25

| Command / gate                                             | Status  | Evidence                                                                                                                                                                                                                                                                                                                                                                                                       |
| ---------------------------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Focused semantic, persistence, API, worker, and web suites | Pass    | Typed semantic parsing/review, Resume Health v2 golden values, killable subprocess timeout/cleanup, generated-contract parsing, accessible review operations, and historical/v2 persistence compatibility pass locally.                                                                                                                                                                                        |
| Live PostgreSQL regression                                 | Pass    | `test_resume_repository.py` passes against the real migrated PostgreSQL service with a v2 analysis payload and owner-scoped retrieval.                                                                                                                                                                                                                                                                         |
| `scripts/verify-phase2.ps1`                                | Pass    | The exact implementation-tree gate exited 0 on 2026-07-26 in about 8m25s. Contract drift, formatting, lint, strict types, builds, 388 backend, 137 API, 84 worker, 155 web, 12 UI, 3 contract, 4 ESLint-boundary, and 2 edge tests passed; core runtime/recovery, fresh and rollback/forward migrations, 39 live integrations, and 3 Playwright journeys with 1 intentional mobile duplicate skip also passed. |
| `scripts/security-scan.ps1`                                | Pass    | The separate gate exited 0 on 2026-07-26 in about 146 seconds. Gitleaks, pnpm audit, and pip-audit found no secret or known application-dependency vulnerability; all four application images passed the fixable-high Grype gate. API and worker retain only the three documented nonblocking medium CPython findings whose listed fixes require Python 3.15 prereleases.                                      |
| Hosted CI                                                  | Pending | No branch was pushed and no PR was opened. Publishing the locally verified closure for hosted CI requires explicit user authorization.                                                                                                                                                                                                                                                                         |

### Known limitations and deferred work

- OCR is an explicit port but no provider is enabled; image-only PDFs produce a
  parser warning and insufficient-data report rather than invented text.
- The deterministic fictional corpus now covers one- and two-column PDF, DOCX,
  image-only PDF, header/footer exclusion, table-heavy content, locale/date
  precision, concurrent roles, unusual fonts, bidirectional controls, and long
  resumes. Malformed, encrypted, polyglot, macro, traversal, archive-expansion,
  forced-timeout, and scanner cases are generated safely in isolated tests.
- PDF has an authoritative extractor page-count cap. The local `python-docx`
  path cannot reliably infer rendered DOCX pages, so DOCX is instead bounded by
  upload bytes, archive entries, expanded bytes/ratio, extracted characters/
  blocks, and artifact size. Layout-aware DOCX page enforcement requires a later
  rendering provider.
- The local semantic parser is deliberately conservative and deterministic. It
  marks uncertainty for human review instead of inventing facts; richer
  provider-backed inference remains behind the parser port and must satisfy the
  same schema and grounding rules.
- Resume Health is job-independent document analysis. It does not create the
  career-profile/evidence source of truth, verify a claim, measure role/job fit,
  call an AI provider, or predict hiring outcomes.
- Explicit document deletion covers Phase 2 objects and relational content.
  Account-wide export/erasure, backups, legal retention, production lifecycle,
  support access, managed storage/scanner/queue selection, and restore exercises
  remain Phase 10 release work.
- Local Compose hardening and ClamAV prove the development contract, not an
  internet-facing production sandbox or zero-day immunity.
- The isolated child process provides killable parser timeout and cleanup. The
  worker/container limits remain defense in depth; Windows cannot enforce the
  POSIX child `rlimit` controls, so the Linux production/runtime path remains the
  authoritative resource-limit environment.
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

## Phase 3 scope and status

Current status: **the evidence graph, eligibility policy, and core career CRUD
slice is complete and hosted verified; resume-ready Career Record closure is
locally verified with hosted closure evidence pending authorization**.
Implementation commit `0df8bcf` records the historical Phase 3
local-verification tree. No-change trigger commit `f752b55` has the identical
tree and passed hosted CI run `29657932938` on PR #13 against the Phase 2 hosted
baseline branch `codex/phase-2-resume-health`. The current tree adds explicit
fact/entity/skill confirmation, canonical per-field provenance, personal/contact
facts, and explicit experience-project relationships alongside the existing
achievement/evidence graph.

### Implemented vertical slice

- [x] Migration `20260715_0004` adds owner-scoped career profiles, typed career
      entities and skills, evidence items with immutable revisions/sources/
      metrics/links/usage/conflicts, resume import proposals, private attachment
      admission/processing/outbox/cleanup/audit records, achievement drafts,
      reminder preferences, and Career Record audit events with ownership-aware
      foreign keys, constraints, indexes, and positive versions.
- [x] `rezumi.modules.career_record` is one transactional bounded context with
      framework-free domain rules and application ports. It owns career truth,
      evidence authority, eligibility, conflicts, proposals, Achievement Inbox,
      reminder preferences, and redacted audit; SQLAlchemy, Resume Health source,
      S3, ClamAV, extraction, API, and Celery adapters point inward.
- [x] Career Profile supports profile facts, experience, education, projects,
      certifications, awards, volunteering, publications, languages, skills,
      partial year/year-month dates, complete-set accessible reorder, explicit
      promotion/concurrent-role grouping, neutral gap findings, optimistic
      concurrency, and owner-scoped CRUD without requiring a resume.
- [x] Personal/contact facts, career entities, and skills have explicit
      confirmation. Material edits revoke confirmation; downstream readiness
      exposes only current confirmed records and makes confirmed personal facts
      available to appropriate document consumers.
- [x] Per-field provenance records the exact reviewed semantic field identity,
      anchors, snapshot revision/schema/parser, origin, canonical value digest,
      and accept-time owner edits. Current provenance is revalidated against the
      immutable source rather than trusted by row presence alone.
- [x] Experience-to-project relationships are explicit owner-scoped edges.
      Achievement-to-entity and evidence-to-entity/skill relationships remain in
      their existing authoritative structures.
- [x] Resume-derived changes are copied into versioned pending proposals through
      an explicit ownership-checked Resume Health source query. Accept, edited
      accept, and reject are explicit actions; source deletion never rewrites
      accepted career truth and makes source-only Supported evidence ineligible.
- [x] The new typed semantic proposal flow reads the owned reviewed Phase 2
      sidecar server-side, excludes unreviewed/removed fields, retains missing
      facts as questions, and maps accepted candidates to canonical facts,
      skills, experiences, education, projects, or certifications. Legacy generic
      proposals remain readable; their v1 creation route is deprecated.
- [x] Evidence Vault separates active/archive/delete lifecycle from Verified,
      Confirmed, Supported, Inferred, and Unsupported strength. State transitions,
      immutable revisions, source availability, numeric dimensions, conflicts,
      and downstream factual/numeric eligibility are deterministic and owner
      scoped. Client input and owner confirmation cannot produce `Verified`; no
      independent verification authority is configured in production.
- [x] Evidence attachments accept bounded PDF/DOCX only. Short-lived exact-
      operation signed transfers use randomized private keys; finalize rechecks
      owner, expiry, size, media type, and signature. A restricted worker scans
      fail-closed and extracts bounded counts through durable jobs, outbox,
      execution fencing, bounded retries/dead letters, lost-delivery
      reconciliation, and durable private-object cleanup. An attachment alone
      never raises evidence strength or eligibility.
- [x] Achievement Inbox supports neutral guided capture, durable incomplete
      drafts, structured metric context, experience/project association, recurring
      reminder preferences, archive, and an explicit idempotent conversion to one
      Confirmed evidence item.
- [x] Authenticated Next.js routes at `/career-profile`, proposal review,
      `/evidence`, evidence detail, and `/achievement-inbox` use real APIs and
      implement loading, empty, success, validation, conflict, and safe error
      states with semantic timelines/tables, keyboard controls, visible labels,
      focus handling, reduced-motion support, and responsive overflow. No working
      Phase 1/2 path was replaced with fixtures or mock data.

### Architecture decisions realized

- ADR 0009 extends the source-of-truth, ownership, and asynchronous processing
  decisions with one Career Record consistency boundary. Account display and
  search preferences remain in Phase 1 `user_profiles`; factual career
  presentation belongs to `career_profiles` and is not dual-written.
- Every public resource identifier is a UUID, every mutable aggregate uses a
  positive version, and API/service authorization fetches by owner plus ID.
  Mutations require the existing authenticated session and CSRF policy; nested
  links validate both ends in the same owner scope and unknown/cross-user IDs are
  indistinguishable.
- Evidence strength is server-derived. Manual/URL claims begin Inferred, exact
  validated resume spans can begin Supported, owner attestation can become
  Confirmed, and only the unconfigured server-side verification-authority port
  could produce Verified. Material edits invalidate prior strength by creating an
  immutable Inferred revision.
- Downstream modules receive evidence through the owner-scoped application
  eligibility query rather than ORM filtering or a client-selected state. Open
  conflicts, unavailable provenance, archive/delete lifecycle, Inferred, and
  Unsupported are excluded; numeric use additionally requires complete decimal
  value/unit/period/precision/attribution context and confirmation.
- Career Record attachments deliberately have separate persistence from Resume
  Health documents while using provider-neutral storage/scanner/extractor ports.
  The worker queue payload contains durable identifiers only, and a scheduled
  database-only reconciler repairs lost delivery or expired leases within
  separate processing/recovery budgets.

### Migration and compatibility

`20260715_0004` depends on the verified Phase 2 head `20260715_0003`. It is
additive: Phase 1/2 tables and routes are neither renamed nor removed. Fresh
bootstrap and the required `0003 -> 0004 -> 0003 -> 0004` path have been exercised
locally. The downgrade deletes Phase 3 relational data in dependency order;
production rollback after real career/evidence content therefore requires export,
retention, and forward-repair review rather than an automatic downgrade.

Additive closure migration `20260726_0011` depends on the Phase 9 head
`20260724_0010` and adds confirmation, personal-fact, typed-proposal,
relationship, and per-field-provenance tables without rewriting historical
Career Record rows. It also conditionally repairs canonical Phase 9 objects for
long-lived pre-release databases stamped by earlier development copies of
revision `0010`; missing metadata is backfilled deterministically, conflicting
data aborts the transaction, and no Phase 9 record is deleted. The isolated test
upgrades a deliberately degraded `0010` database, checks metadata parity,
rejects cross-owner confirmation and duplicate primary facts, downgrades to
`0010`, and repairs forward to a single matching head. Downgrade deletes closure
records but deliberately preserves objects owned by Phase 9; it is not a
production rollback recommendation after users create closure data.

### Verification evidence and remaining gate

The preceding Phase 2 acceptance criteria were rechecked before Phase 3 edits:
the complete Phase 2 verifier passed in 208.5 seconds. Focused Phase 3 evidence
captured during implementation, the final local closeout result, and hosted CI
evidence are listed below.

| Command / gate                                     | Status | Evidence                                                                                                                                                                                                                                                                                                                                                         |
| -------------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pre-edit `scripts/verify-phase2.ps1`               | Pass   | The complete Phase 2 migration, integration, runtime, browser, build, and cleanup baseline remained green in 208.5 seconds.                                                                                                                                                                                                                                      |
| Backend unit/architecture suites                   | Pass   | Ruff and mypy passed; 132 backend architecture/unit tests passed, including Career Record state, eligibility, ownership, concurrency, grouping, proposals, conflicts, achievements, migration shape, and attachment workflow tests. Final local closeout rerun: 132 passed in 4.30 seconds.                                                                      |
| Worker unit suite                                  | Pass   | Ruff and mypy passed; 63 worker tests passed, including attachment queue routing, bounded task behavior, production composition, outbox, cleanup, fencing, and stale-job reconciliation. Final local closeout rerun: 63 passed in 1.18 seconds.                                                                                                                  |
| API focused/full iteration                         | Pass   | The final-tree API suite passed 92 tests in 8.97 seconds with one non-blocking Starlette/httpx2 deprecation warning. It includes the production Career Record and attachment workflow composition test.                                                                                                                                                          |
| Web quality, component, and build                  | Pass   | Prettier, generated-contract drift, ESLint/boundary checks, TypeScript, 3 contract tests, 12 UI tests, 81 web tests, 2 web-edge tests, and the production Next.js build passed with all Phase 3 routes present.                                                                                                                                                  |
| Real dependency integration                        | Pass   | 11 PostgreSQL/Redis/MinIO/ClamAV provider/repository integrations passed in 2.55 seconds. Fresh migration, `0004 -> 0003 -> 0004` round trip, container migration idempotency, runtime probes, and Celery broker ping all passed.                                                                                                                                |
| Primary Phase 3 E2E                                | Pass   | The isolated Playwright run passed 4 workflows in 55.1 seconds with 2 intentional mobile skips: desktop auth/onboarding, desktop Career Record, guest Resume Health, and mobile auth passed. The Career Record workflow registers and verifies a user, creates profile/skill/project/experience data, confirms evidence, and explicitly converts an achievement. |
| `scripts/verify-phase3.ps1` / `make verify-phase3` | Pass   | `scripts/verify-phase3.ps1` passed locally on 2026-07-19 against the documentation-aligned tree. It ran the full repository gate followed by the isolated Phase 3 migration, integration, runtime, and browser workflow.                                                                                                                                         |
| Hosted CI                                          | Pass   | Run `29657932938` passed supply-chain, API, web/contracts, worker, browser-smoke, Resume Health E2E, Career Record E2E, and container/image jobs on no-change trigger commit `f752b55`, whose tree is identical to implementation commit `0df8bcf`; GitGuardian also passed on PR #13.                                                                           |

### Resume-ready closure evidence — 2026-07-26

| Command / gate                           | Status | Evidence                                                                                                                                                                                                                                                                                                                                                                                                |
| ---------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Focused backend/API closure portfolio    | Pass   | 48 semantic import, confirmation, provenance, relationship, readiness, and route tests pass; the broader identity plus Career Record selection passes 70 tests.                                                                                                                                                                                                                                         |
| Isolated migration integration           | Pass   | A deliberately degraded `20260724_0010` schema upgrades to `20260726_0011`; canonical Phase 9 objects are repaired without deleting rows, `alembic check` reports no drift, historical records remain unconfirmed, ownership/primary-fact constraints fail closed, downgrade preserves Phase 9 repairs, and forward repair returns one matching head.                                                   |
| Real PostgreSQL Career Record repository | Pass   | 5 tests pass, including confirmation, facts, provenance, relationships, cross-owner filtering, and relationship cascade behavior. The full fresh-database dependency portfolio passes 41 tests with 9 inherited cyclic-FK ordering warnings.                                                                                                                                                            |
| Full host quality and build portfolio    | Pass   | Prettier, contract/lock drift, repository boundaries, Ruff, mypy, strict TypeScript, production builds, 398 backend, 145 API, 84 worker, 163 web, 12 UI, 3 contract, 4 frontend-boundary, and 2 web-edge tests pass. The FastAPI portfolio retains one non-blocking Starlette/httpx2 deprecation warning.                                                                                               |
| `scripts/verify-phase3.ps1`              | Pass   | The exact cumulative gate passed in 336.3 seconds on 2026-07-26. It freshly recreated the primary containers while retaining named volumes, verified migration head `20260726_0011`, health and Celery, then used an isolated project for rollback to `20260715_0003`, forward repair, all 41 integrations, runtime failure/recovery probes, and 4 Playwright journeys with 2 intentional mobile skips. |

Earlier exact attempts are retained as failure evidence rather than relabeled:

- Docker Desktop returned `unexpected EOF` while `docker wait` observed the
  isolated MinIO initializer; the project cleanup succeeded. A direct isolated
  retry then passed in 179.4 seconds.
- A later primary probe saw a stale Mailpit host-port attachment even though the
  container reported healthy. Recreating that container restored HTTP 200.
- The verifier now recreates primary containers without deleting named volumes,
  retries bounded HTTP probes, and retries only Docker CLI transport failures
  while waiting for the initializer. Persistent non-200 responses, nonzero
  initializer exits, and exhausted retries still fail.
- GNU Make is unavailable in this PowerShell environment, so the attempted
  `make format-check` remains recorded as unavailable; the exact PowerShell gate
  runs the pinned underlying command portfolio and passed.

### Known limitations and deferred work

- No independent verification provider or operating process is configured.
  Production evidence can be Confirmed or Supported but not Verified; owner
  confirmation is intentionally not relabeled as independent verification.
- Evidence attachments accept PDF and DOCX only and use the local ClamAV and
  bounded parser adapters. OCR is disabled, DOCX has no authoritative rendered
  page count, and parser timeouts still use `asyncio.to_thread` rather than a
  killable per-file subprocess. These are not production-sandbox guarantees.
- Phase 3 records an external HTTP(S) URL only as provenance metadata; it does not
  fetch the URL. SSRF-hardened job import belongs to Phase 5.
- The Phase 3 attachment intent is kept in the mounted page, not durable browser
  storage. Reload after admission can consume one attachment slot until the
  default ten-minute intent expires; multipart/resumable upload is absent.
- The career-record Playwright primary workflow is desktop-only. Existing shared
  workspace navigation and responsive component coverage exercise mobile paths,
  but there is no separate mobile run of proposal review, private attachment
  processing, or the complete career journey.
- Complete account export/erasure, backup retention and restore, legal holds,
  production storage/scanner/queue selection, and administrator support access
  remain Phase 10 work. Phase 3 owner-scoped delete and object cleanup do not
  substitute for account-wide orchestration.

## Phase 4 scope and status

Current status: **complete**. The active tree adds Role Explorer and Role
Readiness as a production vertical slice. The full local Phase 4 PowerShell gate
passed on 2026-07-19 and covers formatting, linting, type checking, tests,
builds, migrations, integration, runtime probes, worker hardening checks, and the
isolated Role Explorer browser journey. Hosted Phase 4 CI evidence has not yet
been recorded.

### Included

- [x] Migration `20260719_0005` adds public versioned role taxonomy tables,
      competencies, owner-scoped saved roles, readiness analyses, components,
      competency results, evidence links, idempotency records, and redacted
      audit events.
- [x] Seed a Rezumi-authored taxonomy version
      `rezumi-seed-roles/2026-07-19` with Product Manager, Software Engineer,
      and Data Analyst definitions and deterministic UUIDs.
- [x] Add `rezumi.modules.role_readiness` with framework-independent domain
      entities, deterministic fixed-point scoring, application service/ports, and
      SQLAlchemy infrastructure.
- [x] Consume Phase 3 Career Record through
      `CareerRecordService.readiness_snapshot`; the role module does not query
      Career Record tables or trust client-supplied evidence IDs.
- [x] Expose authenticated `/api/v1/roles`, `/api/v1/saved-roles`, and
      `/api/v1/role-readiness` routes with server-side input validation,
      owner-scoped authorization, CSRF, `If-Match`, idempotency, safe problems,
      no-store responses, and generated OpenAPI contracts.
- [x] Build the authenticated `/role-explorer` web workflow with role search,
      save/update/delete, analysis, evidence-linked result tables, history,
      comparison, loading/empty/success/error states, keyboard-named controls,
      and the canonical score disclaimer.
- [x] Add unit, migration-shape, API, repository integration, web component, and
      full-stack Playwright coverage for the primary workflow.
- [x] Add ADR 0010 and update API, architecture, scoring, security, testing,
      checklist, README, Make, CI, and isolated E2E scripts for Phase 4.

### Pre-edit review and acceptance baseline

The preceding Phase 3 acceptance criteria were rechecked before Phase 4 edits:
hosted CI run `29658296318` on implementation commit `65face5` passed every
published Phase 3 job. The Phase 3 implementation already proved account-owned
Career Profile, Evidence Vault, Achievement Inbox, attachment processing,
eligible-evidence exclusion, and the isolated Career Record browser journey.

Reviewed before editing:

- Repository rules in `AGENTS.md`, especially source-of-truth, provenance,
  owner-scoping, generated-contract, and verification requirements.
- ADRs 0002, 0003, 0005, 0007, 0008, and 0009. ADR 0009 was the blocking
  architecture constraint for this phase: Role Readiness must use Career Record
  through an application query boundary.
- The attached UI/product reference for Role Explorer: role search/select without
  job text, saved roles, evidence-linked readiness, compare two or three roles,
  history, loading/empty/error/success states, and no hiring-probability claims.
- `docs/scoring-methodology.md`, including the canonical internal-score
  disclaimer and Role Readiness dimension weights.

### Blocking technical debt assessment

No unresolved technical debt blocks the Phase 4 slice. The only blocking debt
identified before implementation was a potential cross-module persistence leak:
Role Readiness needed profile/evidence inputs but must not query Career Record
tables. That is addressed by `CareerRecordService.readiness_snapshot`, which
returns a bounded owner-scoped snapshot of profile signals and eligible evidence
through the Phase 3 application boundary.

### Verification evidence

| Check                                            | Status | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ------------------------------------------------ | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pre-edit Phase 3 baseline                        | Pass   | Hosted CI run `29658296318` passed the previous implementation tree before Phase 4 edits.                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| Backend focused Ruff and mypy                    | Pass   | `uv run --package rezumi-backend ruff check ...` and `uv run --package rezumi-backend mypy` pass for the new backend surface.                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Backend focused unit/migration tests             | Pass   | Role Readiness scoring/service/migration plus migration-graph tests passed (`9 passed`).                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| API focused Ruff, mypy, and tests                | Pass   | API Ruff, mypy, `tests/test_role_readiness_routes.py`, and `tests/test_contract_export.py` pass (`3 passed`, one Starlette deprecation warning).                                                                                                                                                                                                                                                                                                                                                                                                                 |
| Generated contracts                              | Pass   | `pnpm contracts:generate` updated the normalized OpenAPI artifact and generated TypeScript schema from FastAPI. `pnpm contracts:check`, contracts build, and the unchanged web typecheck pass; additive response defaults preserve existing client fixtures.                                                                                                                                                                                                                                                                                                     |
| Web focused Prettier, lint, typecheck, component | Pass   | Role Explorer files format; `pnpm --filter @rezumi/web lint`, `typecheck`, and focused Vitest pass (`3 passed`).                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| Phase 4 E2E discovery                            | Pass   | With `PLAYWRIGHT_E2E_MODE=full-stack`, Playwright lists the Role Explorer desktop/mobile projects; the spec desktop path runs in the isolated Phase 4 stack.                                                                                                                                                                                                                                                                                                                                                                                                     |
| Final repository gates                           | Pass   | `scripts/verify-phase4.ps1` passed on 2026-07-19. It runs the documented PowerShell equivalent of the Make gate in this native shell: formatting, lock/contract drift, lint, type checking, unit suites, production builds, Docker Compose config/build/startup, migration head/rollback/forward repair, real dependency integrations, runtime probes, worker hardening checks, and Phase 4 E2E. GNU Make is not installed in this PowerShell environment; an earlier `make format-check` attempt failed with command-not-found and was not treated as evidence. |

A previous final-verification attempt exposed a non-product infrastructure gap:
fresh ClamAV volumes can spend several minutes downloading the initial database
while the scanner is still unavailable. The PowerShell and POSIX isolated-stack
runners now wait explicitly for the ClamAV service healthcheck before provider
integration tests execute. The final rerun passed after that readiness fix.

### Known limitations and deferred work

- The Phase 4 taxonomy is a small Rezumi-authored seed, not an external labor
  market taxonomy. External provider ingestion, admin curation, localization,
  market calibration, and taxonomy lifecycle operations remain future work.
- Role Readiness is a general role comparison, not an exact job match. It does
  not import job descriptions, fetch URLs, extract source-spanned job
  requirements, or compute Application Readiness; those remain Phase 5.
- The deterministic keyword/relevance matcher is intentionally conservative and
  explainable. It does not use embeddings, model inference, or semantic
  retrieval; future improvements require new formula/config versions and tests.
- The primary Role Explorer E2E workflow is desktop-only, while inherited auth
  and shared workspace suites continue to cover mobile navigation and shell
  behavior.

## Phase 5 scope and status

Current status: **complete and hosted verified**. Phase 5 adds the Job Match,
Requirement Matrix, and Opportunity Prioritizer vertical slice. It preserves
Phase 3 evidence authority and Phase 4 role context while adding exact job
imports, source-spanned requirements, SSRF-hardened URL fetching, deterministic
Application Readiness, hard-gap visibility, and explainable pursuit priority.
PR #20 merged the Phase 5–7 stack at `f9807dc` after hosted CI run `30119088488`
passed all required jobs.

### Included

- [x] Add migration `20260719_0006` for owner-scoped job postings,
      source-spanned job requirements, requirement matches, job-match analyses,
      components, evidence links, opportunity-priority analyses, idempotency
      records, and redacted audit events.
- [x] Add `rezumi.modules.job_match` with framework-independent domain
      entities, deterministic extraction/matching/scoring, application service
      and ports, safe URL-import provider interface, and SQLAlchemy
      infrastructure.
- [x] Consume Career Record only through the existing owner-scoped readiness
      snapshot and Role Explorer context through explicit role identifiers where
      provided; do not query Phase 3 or Phase 4 tables across module boundaries.
- [x] Expose authenticated `/api/v1/jobs`, `/api/v1/jobs/import`,
      `/api/v1/job-match-analyses`, and `/api/v1/opportunity-priorities` routes
      with server-side validation, owner-scoped authorization, CSRF,
      `If-Match`, idempotency, safe problems, no-store responses, and generated
      OpenAPI contracts.
- [x] Build the authenticated `/job-match` web workflow with paste/manual/URL
      import, saved job list/detail, analysis, requirement-to-evidence matrix,
      hard gaps, opportunity priority, loading/empty/success/error states,
      keyboard-accessible controls, semantic tables, and the canonical score
      disclaimer.
- [x] Add unit, SSRF/provider, migration-shape, API, repository integration, web
      component, and full-stack Playwright coverage for the primary workflow.
- [x] Add ADR 0011 and update API, architecture, scoring, security, testing,
      checklist, README, Make, CI, and isolated E2E scripts for Phase 5.

### Pre-edit review and acceptance baseline

The preceding Phase 4 acceptance criteria remain satisfied in the current
working tree: `scripts/verify-phase4.ps1` passed on 2026-07-19 after the final
documentation-aligned closeout, including migration rollback/forward repair, real
dependency integrations, worker hardening probes, and the isolated Role Explorer
browser journey. Hosted Phase 4 CI evidence is not yet recorded and remains a
release-management follow-up, but it does not change the local acceptance result
for this phase handoff.

Reviewed before editing:

- Repository rules in `AGENTS.md`, especially source-of-truth, provenance,
  owner-scoping, generated-contract, URL-import security, and verification
  requirements.
- ADRs 0003, 0005, 0008, 0009, and 0010. ADRs 0009 and 0010 constrain this
  phase to use application boundaries for eligible evidence and role context.
- The attached UI/product reference for Job Match: left-navigation workspace,
  exact job comparison, source-spanned requirements, match matrix, hard gaps,
  opportunity priority, loading/empty/error/success states, and no
  hiring-probability claims.
- `docs/scoring-methodology.md`, including the canonical internal-score
  disclaimer, Application Readiness formula, match credits, mandatory gap rules,
  and opportunity-priority cautions.
- `docs/security-threat-model.md`, especially SSRF threat T09, remote content
  injection T10, and prompt-injection T18.

### Blocking technical debt assessment

No unresolved technical debt blocked the Phase 5 slice. The most important
implementation debt was to avoid a new cross-module persistence leak: Job Match
needed eligible evidence and optional role context, but had to consume those
through application boundaries rather than reading Career Record or Role
Readiness tables. That is addressed through the Career Record readiness snapshot
and Role Readiness application service. The URL importer uses deterministic local
tests and explicit SSRF validation so tests do not require external network
access or third-party credentials.

### Verification evidence

| Check                               | Status | Evidence                                                                                                                                                                                                                                                                                                                                                                                |
| ----------------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pre-edit Phase 4 baseline           | Pass   | `scripts/verify-phase4.ps1` passed on 2026-07-19 on the final documentation-aligned tree.                                                                                                                                                                                                                                                                                               |
| Backend focused tests               | Pass   | Job Match scoring, service, URL-import provider, migration-shape, and migration-graph tests passed before the full gate (`10 passed`).                                                                                                                                                                                                                                                  |
| API and web focused tests           | Pass   | `apps/api/tests/test_job_match_routes.py` passed (`2 passed`, one Starlette deprecation warning). `apps/web/src/modules/job-match/tests/job-match-view.test.tsx` passed (`3 passed`).                                                                                                                                                                                                   |
| Generated contracts                 | Pass   | `pnpm contracts:generate` updated the normalized OpenAPI artifact and generated TypeScript schema from FastAPI. `pnpm contracts:check`, contracts build, and the unchanged web typecheck pass; additive response defaults preserve existing client fixtures.                                                                                                                            |
| Final repository and Phase 5 gates  | Pass   | `scripts/verify-phase5.ps1` passed on 2026-07-19. It runs the native PowerShell equivalent of the Make gate plus the isolated Phase 5 stack: format, uv lock, contract drift, lint, typecheck, JS tests, JS build, Ruff, mypy, backend/API/worker tests, Compose config/build/startup, migrations, runtime probes, integration tests, worker hardening probes, and Playwright journeys. |
| Phase 5 E2E and integration details | Pass   | Isolated stack migration head was `20260719_0006`; rollback to `20260719_0005` and forward repair passed. Backend integration tests passed (`13 passed`). Playwright ran auth, Resume Health, Career Record, Role Explorer, and Job Match journeys with `6 passed, 4 mobile skips` where product-specific desktop journeys intentionally skip mobile.                                   |

Earlier verification attempts found and fixed two issues caused by the Phase 5
change: the web Vitest suite could exhaust memory with parallel jsdom workers, so
`apps/web/vitest.config.mts` now disables file-level parallelism; and the Job
Match E2E success assertion matched both the screen-reader live region and the
visible alert, so the test now asserts the accessible status region.

### Known limitations and deferred work

- The URL importer validates each URL and redirect resolution before fetching and
  blocks non-public addresses, but it does not yet pin the TCP socket to the
  prevalidated address. Production hardening should add socket pinning or an
  egress proxy/firewall that enforces the same policy outside application code.
- Requirement extraction and evidence matching are deterministic and
  conservative. There is no AI extraction, embedding retrieval, semantic search,
  or provider-backed independent evidence verification in Phase 5.
- URL import supports bounded plain-text and HTML responses and strips script,
  style, and template content. It does not execute remote scripts, send cookies,
  import authenticated pages, or fetch Career Record evidence URLs.
- Opportunity Priority uses the exact job analysis plus user-supplied
  preferences, deadline, effort, and contact count. It is not an application CRM,
  hiring probability, employer score, or ATS score.
- The primary Job Match Playwright workflow runs on desktop. Shared authenticated
  shell, navigation, and auth workflows still cover mobile; a full mobile Job
  Match workflow remains optional future coverage.

## Phase 6 scope and status

Current status: **complete and hosted verified**. Phase 6 adds Change Studio and
truth-locked AI: an authenticated, owner-scoped review workflow that turns
eligible Career Record evidence plus saved Job Match requirements into
structured, grounded suggestions. Provider output remains untrusted until strict
schema validation, deterministic grounding, and explicit user action complete.
The merged Phase 5–7 stack passed hosted CI run `30119088488` on PR #20.

### Included

- [x] Migration `20260719_0007` adds owner-scoped change sets, operations, claim
      ledger entries, clarifying questions, immutable versions, provider run
      metadata, idempotency records, and redacted audit events.
- [x] `rezumi.modules.change_studio` provides framework-independent domain
      types, provider gateway ports, deterministic local provider, strict
      candidate validation, grounding verifier, application service, and
      SQLAlchemy persistence.
- [x] Change Studio consumes eligible evidence through Career Record application
      services and saved job requirements through the Job Match application
      service; clients cannot attach arbitrary evidence or requirement IDs.
- [x] Authenticated `/api/v1/change-sets` routes and operation action routes
      enforce CSRF, idempotency keys, ETags, owner authorization, input
      validation, no-store responses, safe problem details, and generated
      OpenAPI contracts.
- [x] The authenticated `/change-studio` workflow covers loading, empty,
      success, and error states; provenance-visible diffs; accessible action
      controls; explicit accept/reject/edit/alternate/lock/undo/redo/restore
      actions; and unsupported-claim/question handling.
- [x] Backend unit/adversarial tests, API authorization tests, repository
      integration tests, web component tests, and full-stack Playwright coverage
      exercise the primary workflow.
- [x] API, architecture, security, testing, grounding, README, checklist,
      Make/CI/verification scripts, and this plan are updated for Phase 6.

### Pre-edit review and acceptance baseline

The preceding Phase 5 acceptance criteria remain satisfied in the current
working tree based on the recorded final gate: `scripts/verify-phase5.ps1` passed
on 2026-07-19 after documentation and contract drift were aligned. That gate
includes the platform verifier, migration head `20260719_0006`, rollback to
`20260719_0005`, forward repair to head, backend integration tests, worker
hardening probes, and the authenticated Job Match Playwright journey. The Phase 5
known URL-import socket-pinning limitation is contained to future importer
hardening and does not block Change Studio because this phase consumes saved,
owner-authorized Job Match analyses rather than fetching new URLs.

Reviewed before editing:

- Repository rules in `AGENTS.md`, especially Career Record source-of-truth,
  provenance, owner-scoped authorization, generated contracts, AI output
  validation, and phase verification requirements.
- ADR 0004 and `docs/ai-grounding-policy.md` for provider gateway, strict
  schemas, claim ledger, deterministic grounding, user control, immutable
  versions, clarifying questions, and adversarial tests.
- ADR 0003 for deterministic score language and expected-score simulation limits.
- ADR 0009 for the Career Record application-boundary evidence authority and
  stricter numeric eligibility.
- ADR 0011 for the Phase 5 Job Match boundary, source-spanned requirements, and
  saved analysis snapshots.
- The attached UI/product reference for the Change Studio loop: original text,
  suggested text, diff, rationale, evidence, job requirement, accept/reject/edit,
  alternate, undo/redo, restore, and no invented career facts.

### Blocking technical debt assessment

No unresolved technical debt blocks Phase 6. The important implementation risks
are controlled by using application boundaries instead of cross-module table
reads, keeping the local provider deterministic and data-driven, failing closed
when a production provider is not configured, and never treating an expected
score delta as permission to bypass grounding or user approval.

### Verification evidence

| Check                               | Status | Evidence                                                                                                                                                                                                                                                                                                                                                                                                |
| ----------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pre-edit Phase 5 baseline           | Pass   | `scripts/verify-phase5.ps1` passed on 2026-07-19 after documentation and contract drift were aligned. Phase 5 migration head `20260719_0006`, rollback to `20260719_0005`, forward repair, backend integration tests, worker hardening probes, and the authenticated Job Match Playwright journey remain the accepted predecessor baseline.                                                             |
| Focused Change Studio tests         | Pass   | Change Studio backend service, adversarial provider/grounding, migration-shape, migration-graph, API route, repository integration, web component, and focused desktop Playwright tests passed while iterating. The final focused browser rerun passed `apps/web/e2e/change-studio-journey.spec.ts` in 12.1 seconds after the locator was narrowed to avoid repeated evidence text.                     |
| Generated contracts                 | Pass   | `pnpm contracts:generate` updated the normalized OpenAPI artifact and generated TypeScript schema from FastAPI. `pnpm contracts:check`, contracts build, and the unchanged web typecheck pass; additive response defaults preserve existing client fixtures.                                                                                                                                            |
| Final repository and Phase 6 gates  | Pass   | `scripts/verify-phase6.ps1` passed on 2026-07-19. It runs the native PowerShell equivalent of the Make gate plus the isolated Phase 6 stack: format, uv lock, contract drift, lint, typecheck, JS tests, JS build, Ruff, mypy, backend/API/worker tests, Compose config/build/startup, migrations, runtime probes, integration tests, worker hardening probes, and Playwright journeys.                 |
| Phase 6 E2E and integration details | Pass   | Isolated stack migration head was `20260719_0007`; rollback to `20260719_0006` and forward repair passed. Backend integration tests passed (`14 passed`). Playwright ran auth, Resume Health, Career Record, Role Explorer, Job Match, and Change Studio journeys with `7 passed, 5 mobile skips` where product-specific desktop journeys intentionally skip mobile and shared mobile coverage remains. |

Earlier verification attempts found and fixed two issues during Phase 6
closeout. The API production-config test needed explicit non-deterministic AI
provider settings after `AI_PROVIDER` changed from the old fake name to the
Phase 6 provider choices. The Change Studio Playwright journey also used one
broad evidence-text locator that matched multiple intentional UI occurrences;
the assertion now targets a stable visible occurrence.

### Known limitations and deferred work

- The local deterministic provider is conservative and only reuses already
  eligible evidence text. The HTTPS JSON provider is configured behind strict
  schema/grounding controls, but live provider credentials, privacy/legal review,
  data residency, retention, and cost-budget operations remain deployment work.
- Phase 6 versions are Change Studio output versions, not final exportable
  resume documents. Phase 7 owns structured resume editing, rendering,
  round-trip verification, and download controls.
- Expected score effect is a bounded local estimate derived after grounding; the
  service ignores provider-supplied deltas and does not run a new scoring engine
  simulation in Phase 6.
- Plan-level quotas, per-user AI budgets, and production provider observability
  are intentionally deferred to the later entitlement/operations layer.

## Phase 7 scope and status

Current status: **the backend distinct-template, durable asynchronous export,
fidelity, and private-object cleanup closure is implemented and host/integration
verified. The final Phase 7 gate is blocked by two unchanged frontend browser
dependencies; this non-frontend PR does not claim Phase 7 complete**.
Phase 7 provides an authenticated, owner-scoped workflow that turns eligible
Career Record evidence and optional Change Studio output into structured resume
drafts, immutable versions, ATS-readable PDF/DOCX/text/JSON exports, round-trip
verification reports, and short-lived download intents. PR #20 merged at
`f9807dc` after hosted CI run `30119088488` passed every required job.

### Included

- [x] Migration `20260719_0008` adds owner-scoped resumes, immutable resume
      versions, export records, verification reports, short-lived download
      intents, idempotency records, and redacted audit events.
- [x] Additive migrations `20260726_0012` and `20260726_0013` pin structured
      layout/fact data and complete version hashes, add canonical fidelity
      results, operation-typed transactional outbox records, fenced render and
      cleanup leases, pre-write attempt-object cleanup backstops, independent
      cleanup budgets, retry/dead-letter state, and truthful deletion
      timestamps. Inconsistent historical deletion state is returned to queued
      cleanup without discarding an object key or inventing a timestamp.
- [x] `rezumi.modules.resume_builder` provides framework-independent domain
      entities, validation, application services, renderer/extractor/storage
      ports, SQLAlchemy persistence, deterministic local rendering, round-trip
      verification, and private export storage.
- [x] Resume Builder consumes eligible Career Record evidence and optional
      Change Studio output through application boundaries; clients cannot mark
      edits grounded or attach arbitrary evidence as authority.
- [x] Authenticated `/api/v1/resumes`, `/api/v1/resume-versions`, and
      `/api/v1/exports` routes enforce CSRF, idempotency keys, ETags,
      owner-scoped authorization, input validation, no-store responses, safe
      problem details, and generated OpenAPI contracts.
- [~] The unchanged authenticated `/resume-builder` client remains wire-compatible:
  lint, typecheck, component tests, and production build pass with additive
  API fields. It does not poll the new asynchronous export state to terminal
  completion, so its Download browser step remains a frontend dependency and
  is not implemented in this non-frontend closure.
- [x] Five genuinely distinct constrained templates render searchable Unicode
      PDF/DOCX/text/JSON. One canonical `career-resume-fidelity-v1` manifest pins
      version and expected content hashes and independently blocks omissions,
      duplication, order changes, unsearchable output, page overflow, grounding
      failures, unsupported facts/numbers, or hash drift before download.
- [x] Export rendering, independent parsing, verification, failed-object cleanup,
      and user-requested deletion run in the isolated worker. Transactional
      outbox dispatch, allowlisted job operations, fenced leases, bounded
      retries/dead letters, precommitted attempt-scoped cleanup records, and
      scheduled reconciliation make requests reload-safe and recover lost or
      duplicate delivery and crashes after object writes.
- [~] Backend service, renderer, migration, API, repository integration, worker,
  replay, and failure coverage exercises the durable export/verify/delete
  lifecycle. The isolated backend/worker gate passes; the full browser gate
  remains blocked on two explicitly excluded frontend dependencies.
- [x] ADR 0013 and API, architecture, security, testing, checklist, README,
      CI/verification scripts, generated contracts, and this plan are updated
      for the backend Phase 7 closure.

### Pre-edit review and acceptance baseline

The preceding Phase 6 acceptance criteria remain satisfied in the current
working tree based on the recorded final gate: `scripts/verify-phase6.ps1`
passed on 2026-07-19 after documentation and contract drift were aligned. That
gate includes the platform verifier, migration head `20260719_0007`, rollback
to `20260719_0006`, forward repair to head, backend integration tests, worker
hardening probes, grounding/provider tests, and the authenticated Change Studio
Playwright journey. Phase 6's known limitation is contained to production
provider enablement and does not block Phase 7 because Resume Builder consumes
validated versions and eligible evidence rather than trusting provider output.

Reviewed before editing:

- Repository rules in `AGENTS.md`, especially Career Record source-of-truth,
  provenance, owner-scoped authorization, generated contracts, export privacy,
  and verification requirements.
- ADRs 0002, 0004, 0005, 0006, 0007, 0009, 0011, and 0012 for source-of-truth,
  grounding, ownership, isolated document work, generated contracts, eligible
  evidence authority, Job Match snapshots, and Change Studio versions.
- `docs/security-threat-model.md`, especially object access, sensitive-log
  redaction, queue replay/idempotency, render cost, and the new export
  round-trip threat.
- `docs/testing-strategy.md` and `docs/implementation-checklist.md` for
  required loading/empty/success/error, accessibility, authorization,
  migration, integration, and e2e coverage.

### Blocking technical debt assessment

The 2026-07-25 audit identified shared renderer structure and synchronous export
without an exact blocking fidelity manifest as backend release gaps. This closure
implements distinct templates, canonical fidelity, and durable fenced render and
cleanup workers. Evidence authority is preserved through owner-scoped source
snapshots and exact evidence revisions. Structured authoring/history ergonomics
remain a separately owned frontend dependency under the explicit exclusion for
this run.

### Verification evidence

| Check                               | Status  | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ----------------------------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pre-edit Phase 6 baseline           | Pass    | `scripts/verify-phase6.ps1` passed on 2026-07-19 after documentation and contract drift were aligned. Phase 6 migration head `20260719_0007`, rollback to `20260719_0006`, forward repair, backend integration tests, worker hardening probes, grounding/provider tests, and the authenticated Change Studio Playwright journey remain the accepted predecessor baseline.                                                                                                         |
| Historical Phase 7 hosted baseline  | Pass    | PR #20 merged at `f9807dc` after hosted CI run `30119088488`. The historical 2026-07-19 local gate covered migration head `20260719_0008`, rollback/forward repair, backend integrations, worker probes, renderer round trips, and the authenticated Resume Builder workflow.                                                                                                                                                                                                     |
| Closure backend and renderer tests  | Pass    | 41 focused backend unit/migration tests pass on the current tree, covering service policy, canonical manifests, real PDF/DOCX Unicode extraction, exact omission/duplicate/order/searchability/hash/grounding failures, page overflow, render/deletion leases, attempt-key fencing, cancellation immediately after an object write, durable orphan cleanup, retry/dead-letter/reconciliation, storage response controls, legacy deletion recovery shape, and the migration graph. |
| Closure worker and API suites       | Pass    | All 89 worker tests and 145 API tests pass on the current tree. Worker coverage includes typed dispatch, runtime composition/resource disposal, bounded orphan-object reconciliation counts, retry/dead-letter reporting, and scheduler routing.                                                                                                                                                                                                                                  |
| Closure real integrations           | Pass    | The fresh isolated stack reached `20260726_0013`, downgraded to `20260719_0007`, repaired forward to head, and passed all 42 PostgreSQL/Redis/MinIO/provider/repository integration tests with 9 known SQLAlchemy cycle warnings.                                                                                                                                                                                                                                                 |
| Current web compatibility           | Blocked | The unchanged web app passes lint, typecheck, all 163 component/unit tests, and a 49-route production build against the additive generated contract. Its browser client does not poll a truthful `202 pending` export to terminal state, and the inherited Job Match expectation contradicts the rendered mandatory-gap action. No `apps/web` file is changed in this PR.                                                                                                         |
| Generated contracts                 | Pass    | `pnpm contracts:generate` updated the normalized OpenAPI artifact and generated TypeScript schema from FastAPI. `pnpm contracts:check`, contracts build, and the unchanged web typecheck pass; additive response defaults preserve existing client fixtures.                                                                                                                                                                                                                      |
| Current host repository gate        | Pass    | The host/platform portion of `scripts/verify-phase7.ps1` passes: Prettier, uv lock, contract drift, JavaScript lint/boundaries/types/tests/build, Python Ruff/mypy/tests, Compose config/images/startup, migrations, runtime probes, and worker ping. Counts include 427 backend, 145 API, 89 worker, 163 web, 12 UI, 3 contract, 4 boundary, and 2 edge tests; Next.js built 49 routes.                                                                                          |
| Final closure repository/stack gate | Blocked | `scripts/verify-phase7.ps1` exited 1 after its host/platform gate passed because a stale Rezumi test project held port `11025`. After scoped cleanup, the isolated rerun passed head/rollback/repair, 42 integrations, and worker/runtime checks, then ended with 6 browser passes, 6 intentional mobile skips, and 2 unchanged frontend failures described below.                                                                                                                |

Fresh verification on this isolated backend-only branch supersedes earlier
mixed-worktree evidence. No frontend-specific fix from the mixed worktree is
included; the two remaining browser dependencies are recorded below.

The closure implementation gives every render attempt a distinct fenced key and
commits a durable cleanup backstop before writing bytes. The verified winner
cancels that record in the same transaction as its export state; cancellation
after the write, uncertain storage results, failed verification cleanup, lease
loss, and cleanup retry/dead-letter behavior are executable tests. Migration
`20260726_0013` adds the deletion-state constraint and recovers inconsistent
historical `deleted` rows to durable cleanup without erasing their key or
fabricating `deleted_at`.

Docker Desktop recovered and reported server `29.6.2`. The first exact
`scripts/verify-phase7.ps1` attempt passed its complete host/platform gate but
the isolated stack could not bind Mailpit port `11025`; a four-hour-old
`rezumi-e2e-41492` test project owned that port. No active verifier owned the
project, so only its five temporary test containers and disposable volumes were
removed. The primary stack was restored healthy.

The bounded isolated rerun then reached migration head `20260726_0013`,
downgraded to `20260719_0007`, repaired forward, passed all 42 real integration
tests, and completed worker/runtime hardening before Playwright. Six browser
tests passed and six intentional mobile cases skipped; two unchanged frontend
cases failed. Job Match still expects “Prepare a tailored resume” although the
correct mandatory-gap state renders “Address mandatory gaps before tailoring.”
Resume Builder receives a truthful `202 pending` export, and the worker completes
verification, but the unchanged client does not poll `GET /api/v1/exports/{id}`;
it retains the initial pending/zero-byte record, keeps Download disabled, and
times out. Frontend behavior and test changes are explicitly excluded from this
PR, so the final Phase 7 gate remains blocked rather than claimed complete.

### Known limitations and deferred work

- The five templates are deliberately constrained and searchable rather than
  graphics-heavy. Multi-column or highly decorative designs remain out of scope
  until they pass the same exact occurrence, reading-order, searchability, and
  page-limit corpus.
- Evidence-backed addition in the initial web editor reuses available grounded
  evidence-bearing content. A richer evidence picker and field-level compare UI
  can improve authoring ergonomics without weakening server validation.
- Local MinIO, Redis/Celery, and deterministic render/extractor adapters prove
  the product contract, not a production storage/broker topology or vendor SLA.
  Managed provider choice, alert routing, recovery ownership, and deployment
  approval remain Phase 10 owner/release work.
- Broader locale and complex-layout corpus expansion remains useful defense in
  depth; current blocking tests cover exact Unicode PDF/DOCX content and real PDF
  page overflow.

## Phase 8 scope and status

Current status: **complete and hosted verified**.
Phase 8 adds an authenticated, owner-scoped Application Workspace that connects
one exact saved-job revision, one immutable resume version, and the resume's
eligible evidence revisions to application tracking, grounded application packs,
and deterministic consistency results. The final `scripts/verify-phase8.ps1`
run and separate security scan passed on 2026-07-24 for implementation revision
`964cd9c`. PR #21 workflow run `30126993025` passed every required implementation
job at head `645536b`; final evidence-only run `30128304892` also passed at
`c94307e`.

### Included

- [x] Migration `20260724_0009` adds owner-scoped applications, workflow events,
      tasks, notes, application packs, generated documents, idempotency records,
      and redacted audit events with ownership-aware foreign keys, constraints,
      indexes, and optimistic-concurrency versions.
- [x] The already-shipped Phase 6 migration `20260719_0007` remains immutable.
      Migration `20260724_0009` forward-adds nullable
      `evidence_revision_id`, `evidence_revision_number`, and
      `evidence_statement_sha256` to Change Studio claims under an all-null or
      all-complete constraint. Existing claims stay readable and explicitly
      unpinned; they are never backfilled from today's evidence and fail closed
      when Resume Builder or Application Workspace requires grounded generation.
      New Change Studio claims require the complete revision tuple.
- [x] `rezumi.modules.application_workspace` provides framework-independent
      workflow, provenance, pack, consistency, deletion, interview-context, and
      analytics-snapshot policies behind application ports and SQLAlchemy
      persistence. It reads Job Match, Resume Builder, and Career Record only
      through explicit owner-authorizing application services.
- [x] An application pins the exact job ID/version/source SHA-256, analysis and
      typed requirement snapshot, and resume ID/version ID/version number after
      validating the immutable resume's per-claim hashes. It copies evidence ID/
      revision ID/revision number/statement SHA-256. Legacy resume versions
      without that complete immutable claim/evidence ledger are refused rather
      than silently upgraded or treated as grounded.
- [x] Changing the selected resume creates a fresh evidence snapshot and requires
      an explicit reason that is preserved with the previous/next resume and
      evidence revision identifiers in workflow and audit history.
- [x] The stage state machine, terminal outcome/reopen rules, deadlines,
      follow-ups, contacts, referrals, tasks, notes, events, rejection reasons,
      offer summaries, and deletion behavior are enforced server-side.
      Application and task mutations use strict `If-Match`; every nested lookup
      scopes by owner and application parent.
- [x] Application, task, note, event, and pack creates use bounded idempotency
      keys and request fingerprints. The web holds one stable key for one user
      intent, reuses it for an unchanged retry, and rotates it only after relevant
      input changes or a successful mutation. An omitted event time does not add
      a changing clock value to the retry fingerprint.
- [x] The deterministic synchronous pack generator can produce tailored resume,
      cover letter, professional bio, interest/fit answers, recruiter and hiring
      manager messages, referral and LinkedIn notes, follow-up email, interview
      introduction, and achievement summary. Each claim links only to its exact
      pinned evidence revisions and supported requirements; unsupported facts or
      numbers produce blocking findings rather than plausible prose.
- [x] The consistency engine checks source pins, claim/evidence/requirement
      linkage, document hashes, numeric support, and cross-document claim
      agreement. Document deletion replaces sensitive content and links with an
      audited tombstone; application deletion is ownership/version checked and
      leaves a redacted audit event.
- [x] Authenticated `/api/v1/applications` and application-pack APIs enforce
      CSRF on mutations, private no-store responses, safe problems, bounded
      cursor pagination/filter/sort/calendar ranges, stable idempotency, and
      generated OpenAPI contracts. The lightweight application detail excludes
      unbounded child collections. Cursor decoding rejects non-ASCII input before
      decoding, and database stage/outcome constraints match the domain enums.
- [x] `/applications` and `/applications/{applicationId}` provide board, table,
      and calendar representations, non-drag stage actions, lazy on-demand detail
      panels, cursor-based load-more flows, loading/empty/success/error/conflict
      states, conflict-safe authoritative reloads, and complete keyboard-operable
      desktop/mobile workflows. Resume changes persist their new evidence
      snapshot, reason, workflow event, and audit record in one transaction.
- [x] ADR 0014 and API, architecture, security, grounding, testing, checklist,
      README, generated-contract, Make/CI/verification, and this plan surface are
      aligned with the implemented slice.
- [x] No submission, email delivery, social-network action, autonomous stage
      transition, or message-sending endpoint or control was added. Generated
      messages remain user-reviewed text.

### Local closeout evidence — 2026-07-24 / implementation `964cd9c`

| Check                           | Status | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Predecessor Phase 7 gate        | Pass   | `scripts/verify-phase7.ps1` passed on 2026-07-19, including migration head `20260719_0008`, rollback/forward repair, renderer round-trip checks, integrations, and the authenticated Resume Builder workflow.                                                                                                                                                                                                                                                                                                                                           |
| Final Phase 8 consolidated gate | Pass   | `scripts/verify-phase8.ps1` exited 0 in 273 seconds on 2026-07-24. It passed format/contract/lint/type/build gates, emitted 39 production web routes, reported `206 passed` for the backend portfolio, `104 passed` for the API portfolio, and `121 passed` across 35 web files, then passed integration, worker, runtime, and container probes.                                                                                                                                                                                                        |
| Migration and repair            | Pass   | The isolated fresh database reached head `20260724_0009`, downgraded to `20260719_0008`, and repaired forward. Compatibility tests retain the immutable shipped `20260719_0007` migration and verify the nullable/all-complete forward provenance addition, legacy refusal, database enum parity, and a real atomic resume-change transaction.                                                                                                                                                                                                          |
| Phase 8 browser portfolio       | Pass   | Playwright discovered 16 tests and finished with 10 passed and 6 intentional inherited mobile skips. Application Workspace itself passed the complete desktop and mobile workflow against the production web/edge stack: registration, evidence, saved job/analysis, resume and application creation, board/table/calendar, stage changes, task/note/event activity, pack generation/consistency review, and keyboard-safe controls. The configured skips remain only on predecessor product journeys whose mobile coverage is intentionally inherited. |
| Closeout regression portfolio   | Pass   | Backend/API/web coverage verifies downstream refusal of incomplete legacy provenance, stable idempotency when an event omits its time, strict rejection of non-ASCII cursors, and conflict-safe UI reload. Outcome, deletion, audit, source hashing, numeric grounding, request-race protection, pagination, preserved drafts, live counts, and accessible state handling also pass.                                                                                                                                                                    |
| Separate Phase 8 security scan  | Pass   | `scripts/security-scan.ps1` exited 0 in 287.7 seconds on 2026-07-24. Gitleaks was clean; pnpm and pip audits found no known vulnerabilities, with unpublished local workspace packages explicitly skipped; API and worker had no fixable-high findings; and web plus `web-edge` had no vulnerabilities. Three medium Python-runtime findings remain with fixes only in Python 3.15 prereleases and are nonblocking under the current policy while tracked for a stable fix.                                                                             |
| Hosted Phase 8 CI               | Pass   | PR #21 workflow run `30126993025` passed every required job at implementation head `645536b`: GitGuardian, API, worker, web/contracts, supply chain, containers, browser smoke, and every phase E2E job. The first run exposed a test-only pagination assumption; `645536b` made the assertion traverse every cursor page, and the full fresh-database integration suite passed. Final evidence-only run `30128304892` also passed at `c94307e`.                                                                                                        |

### Known limitations and deferred work

- The first pack generator is deterministic and synchronous. It persists
  immutable inputs, document hashes, idempotency, status, consistency, and audit,
  but it does not call a production language provider or durable worker.
  Provider wording and worker throughput may be added only behind the same
  grounding, schema, retry/cost, and consistency rules.
- Generated messages are drafts for explicit user review. Rezumi does not
  submit an application, send email, message a social network, scrape contacts,
  or infer workflow-stage changes.
- A pre-Phase-8 Change Studio claim without the complete revision tuple remains
  readable for audit/history but cannot seed new grounded output. The safe user
  path is to regenerate from currently eligible evidence; automatic backfill
  would misrepresent historical provenance.
- Calendar, contact, and activity records are local workspace data. Phase 9 adds
  local-only reminders, interview preparation, and non-causal analytics.
  External calendar/CRM connectors and consented contact imports remain deferred
  sensitive flows that require a separate approved ADR.
- Production provider selection, queue/worker sizing, load/soak evidence,
  backup/restore, regional deployment, and protected release approval remain
  Phase 10 decisions and cannot be inferred from a healthy local Compose stack.

## Phase 9 scope and status

Current status: **complete and hosted verified**.

Phase 9 is split by ADR 0015 into Interview Prep, a consent-based private
Networking CRM, Career Growth with deterministic Career Health, and
privacy-minimized Career Analytics. All four contexts remain downstream of the
Career Record/evidence authority and consume other phases only through explicit,
owner-authorizing application interfaces.

### Included implementation

- [x] Add evidence-linked STAR stories, a derived Resume Defense Map,
      role/application question banks, mock sessions, private notes/reflections,
      and grounded follow-up drafts without any sending capability.
- [x] Add owner-scoped organizations, consented contacts, tags, private notes,
      interaction/referral history, user-reviewed templates, and idempotent local
      reminders. Never scrape, import without consent, or deliver outreach.
- [x] Add goals, milestones, exact evidence links, learning/certification and
      promotion/internal-mobility plans, immutable quarterly/annual review
      versions, and deterministic Career Health v1.
- [x] Add current eligible achievement history, a skill-evidence dashboard, a
      six-check non-predictive Promotion Readiness report, and an evidence-backed
      annual resume-refresh workflow without silently changing a resume.
- [x] Add complete-watermark, owner-private analytics for applications,
      interviews, offers, rates, roles, industries, sources, resume versions,
      requirement coverage, achievement growth, and readiness history. Suppress
      rates below a five-record denominator, cohort by a validated IANA timezone,
      publish versioned metric/cohort/timestamp/suppression definitions, and use
      correlation-only language.
- [x] Add exact immutable-resume-version outcome segments and grounded
      requirement-coverage trends.
- [x] Add additive migration `0010`, domain/database enum parity, ownership and
      provenance constraints, generated OpenAPI/contracts, durable analytics and
      reminder jobs, accessible desktop/mobile web workflows, and Phase 9
      verification/security gates. The unshipped migration conditionally repairs
      pre-release Phase 8 provenance tuple/check and resume-change event/audit
      enum drift while preserving the immutable shipped `0009` file.
- [x] Complete final adversarial hardening: current-evidence revalidation for
      new Interview and Growth results, irreversible consent-withdrawal redaction,
      server-owned/database-allowlisted consent policy identifiers, purpose-bound
      cursors, race-safe collection quotas, traceable reminder jobs, exact Growth
      update triggers, bounded Analytics sources, and cohort-correct time buckets.
- [x] Publish the locally and security-verified final tree through hosted CI and
      record the exact revision before claiming the phase complete.

### Local closeout evidence — 2026-07-25 / local and security verified

| Check                           | Status | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| ------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Final Phase 9 consolidated gate | Pass   | `scripts/verify-phase9.ps1` exited 0 on the final closeout tree. Contracts, format, lint, type, build, runtime, predecessor, isolated-stack, and browser checks passed: 365 backend, 134 API, 84 worker, and 150 web tests across 43 web files; the production build emitted 48 routes. The wrapper also restored the primary Compose stack after the isolated run and now validates exact service health with bounded recovery retries.                                                                                                                                                                                                                                                                                                                                                                                                    |
| Migration and integration       | Pass   | The isolated database reached migration head `20260724_0010`, rolled back to `20260724_0009`, and repaired forward, including the pre-release Phase 8 drift case. The PostgreSQL integration portfolio passed 39 tests with 7 inherited SQLAlchemy cycle warnings.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| Phase 9 browser portfolio       | Pass   | Playwright completed 12 tests with 6 intentional inherited mobile skips. The complete Interview Prep, Networking, Career Growth, and Career Analytics journey passed on both desktop and mobile against the production web/edge and API/worker stack.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| Closeout regressions            | Pass   | Defense-map validation isolates each story, delayed retries preserve immutable results, and deleted snapshots retain their conflict barrier. Networking organization mutation and contact reassignment share a canonical owner/row lock order. Analytics jointly claims each outbox/job pair, uses a job-version causal acknowledgement fence, measures lease validity after its final watermark, shares its bounded retry budget across API/worker composition, emits safe terminal logs, and preserves account-deletion/audit ownership invariants. Resume-derived exact provenance now hashes the immutable original block, binds the exact statement before persistence, restricts v1 support to statement-only scope, dynamically excludes spoofed legacy rows, and removes stale accepted-import context after a factual entity edit. |
| Separate Phase 9 security scan  | Pass   | `scripts/security-scan.ps1` exited 0 on the closeout tree. Gitleaks found no secret, `pnpm audit` and `pip-audit` found no known application-dependency vulnerability, and every application image passed the fixable-high Grype gate. API and worker now use digest-pinned Python 3.13.14 on Alpine 3.24 with OpenSSL 3.5.7, removing the newly disclosed fixable OpenSSL findings in the older slim image; only the three documented nonblocking medium CPython findings remain, with listed fixes requiring Python 3.15 prereleases. The runner builds images sequentially, uses a fresh repository-local Grype work/cache directory, scans exact image archives with a checksum-verified native Grype release on Windows, and removes only the generated work directory.                                                                |
| Hosted Phase 9 CI               | Pass   | PR #22 workflow run `30161489265` passed every required job at implementation/merge head `1454792`: GitGuardian, API, worker, web/contracts, supply chain, hardened containers, browser smoke, all predecessor E2E journeys, and the complete Phase 9 desktop/mobile career-workspace journey.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |

### Phase 9 non-negotiable boundaries

- Career Record remains the achievement/evidence source of truth. Phase 9 stores
  exact authorized revision/hash references rather than copied present-day facts.
- Application Workspace supplies purpose-minimized interview and analytics
  views; Phase 9 never queries its tables or consumes notes, contacts, offer/
  rejection prose, or application-pack content.
- Networking consent has a dedicated append-only ledger. Phase 1 account-holder
  consent and Phase 8 application contacts are not backfilled as contact consent.
- Career Health is an internal longitudinal maintenance measure and uses the
  canonical scoring disclaimer. Analytics describes observed patterns, never
  causation, prediction, hiring probability, or a guarantee.
- No Phase 9 endpoint, worker, or control sends email, posts to a social network,
  submits an application, scrapes a contact, or changes an external system.

### Known limitations and deferred work

- Contact consent is the account holder's purpose-specific attestation recorded
  by Rezumi; it is not independent proof from the contact. There is no contact
  scraping, bulk import, CRM/calendar connector, outreach delivery, or autonomous
  application action.
- Interview questions and follow-up drafts use deterministic local generation.
  They remain private, review-only, and unsent; no production AI provider is
  enabled by Phase 9.
- Achievement history includes only current eligible evidence whose type is
  exactly `achievement`. Annual resume refresh is an evidence-backed planning
  workflow and never silently rewrites or publishes a resume.
- Promotion Readiness is a six-check preparation status, not an employer
  assessment, promotion forecast, hiring probability, or guarantee.
- Analytics depends on the user's recorded workflow events, suppresses
  rate/average cohorts below five, and reports observed correlations only.
- Account-wide export/deletion and retention, central rate/cost limiting,
  load/soak evidence, backup/restore, production providers, protected release,
  and deployment remain Phase 10.

## Phase 10A scope and status

Current status: **implemented and verified; draft review publication is the
remaining action for this phase**. Phase 10A replaces the misleading
presentation-only seed command with an explicitly fictional, guarded local
PostgreSQL/MinIO graph across Phases 1 through 9. It adds no API route, worker
task, web behavior, commercial/billing model, organization tenancy, production
infrastructure, or PR #23 migration correction.

### Included

- [x] A separate `rezumi.development.local_seed` composition root runs only
      through the Compose `tools` profile and is not imported by API/worker
      delivery applications.
- [x] Before dependency I/O, exact guards require `development`, an explicit
      confirmation, the local `rezumi` database identity/name on an
      allowlisted Compose/loopback host, local path-free MinIO, the
      `rezumi-documents` bucket, matching SSL settings, and migration head
      `20260726_0013`.
- [x] A deterministic UUIDv5 manifest creates 79 visibly fictional rows across
      Identity, Resume Health, Career Record, Role Explorer, Job Match, Change
      Studio, Resume Builder, Application Workspace, and all four Phase 9
      contexts, plus two private source/export objects.
- [x] Confirmed evidence, source spans, claim/number provenance, immutable
      resume/application pins, verified export hashes, analytics suppression,
      and non-causal interpretation remain internally valid.
- [x] Existing immutable rows and deterministic objects are verified before
      mutation; drift fails closed. Missing objects are created once and read
      back. Mutable rows and an existing fixture account/password are preserved.
- [x] The circular Resume Health upload/source-document relationship is created
      in one transaction by deferring only the final upload link until both rows
      exist. No database constraint is weakened.
- [x] `make seed` and `scripts/seed-local.ps1` migrate and execute the guarded
      container. `pnpm fixtures:preview` is renamed and remains explicitly
      presentation-only with no persistence I/O.
- [x] ADR 0018, README, architecture, threat model, testing strategy,
      implementation checklist, and this plan describe the implemented boundary
      and residual risk.

### Verification evidence

| Check                            | Status | Evidence                                                                                                                                                                                                                                                                                                                                                     |
| -------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Pure seed policy and graph tests | Pass   | Focused Ruff plus `pytest packages/backend/tests/unit/test_local_seed.py -q` passed all 20 guard, determinism, provenance/hash, loader, migration-pin, create-once, replay, and object-drift tests. Canonical backend mypy passed 214 source files.                                                                                                          |
| Compose and preview tooling      | Pass   | `docker compose --profile tools config --quiet`, fixture package lint/typecheck, and `pnpm fixtures:preview` passed; the preview printed labeled fictional JSON and performed no database/object I/O.                                                                                                                                                        |
| First PostgreSQL/MinIO execution | Pass   | `scripts/seed-local.ps1` at migration head `20260726_0013` created and verified all 79 rows and both private objects, printed the public fixture password only for the newly created `.invalid` account, and represented Phases 1-9.                                                                                                                         |
| Same-state replay                | Pass   | A second exact wrapper execution preserved the account, verified all 79 rows and both object byte streams, and reported `0 newly created`.                                                                                                                                                                                                                   |
| Full repository verifier         | Pass   | `scripts/verify.ps1` passed Prettier, lock/contract drift, JS lint/boundaries/types/tests/build, Python Ruff/mypy/tests, Compose config, API/worker/web/edge image builds, forced stack recreation, idempotent migrations, five HTTP probes, and Celery broker ping. Counts: 163 web, 12 UI, 3 contracts, 2 edge, 447 backend, 145 API, and 89 worker tests. |
| Restored primary stack           | Pass   | The `rezumi` project is healthy after verification: API, ClamAV, Mailpit, MinIO, PostgreSQL, Redis, web, edge, worker, and scheduler are healthy; the profile-gated seed service is not part of normal startup.                                                                                                                                              |

The first live execution exposed two defects that pure checks could not prove.
The read-only seed container initially lacked a usable temporary directory; it
now receives a bounded 16 MiB `noexec,nosuid,nodev` tmpfs. The following run
reached PostgreSQL and exposed the intentionally circular Resume Health foreign
keys; the transaction now inserts the upload without its final link, inserts the
source document, then establishes that link before commit. The rejected
transaction created no partial rows. Deterministic objects written before the
rejected transaction were verified and preserved by the successful run rather
than overwritten.

### Known limitations and deferred work

- This is local development data, not a production bootstrap, import, backup
  restore, public demo-account provider, or source of real career claims.
- Every later schema head intentionally reopens the migration-pin review.
  Commercial rows, organization tenancy, privacy workflows, administration,
  limits/cost controls, and production release work remain in their owning
  Phase 10 PRs.
- No browser journey is added because Phase 10A exposes no user-facing route or
  UI behavior; the real acceptance surface is the guarded database/object replay.

## Full-specification completion audit

Historical phase gates remain evidence for the vertical slices they actually
tested; they do not waive requirements that the 2026-07-25 audit found absent or
partial. Phase 2 semantic closure is implemented and locally/security verified;
Phase 1/3 closure is locally verified and its hosted PR remains open. The
backend-only Phase 7 closure is verified in draft PR #24 while its two excluded
frontend browser dependencies remain honestly blocked. Phase 10A is locally
verified in the current branch. Remaining work proceeds in dependency-ordered
reviewable changes:

1. Review and merge the existing stacked closure PRs separately without
   weakening their recorded blockers or expanding their scope.
2. Implement commercial/billing, Coach/Organization tenancy, durable workflows,
   privacy/export/retention/deletion, protected administration, security/cost
   hardening, and production infrastructure/release work as separate phases.

External pricing, provider accounts, legal text, support contacts, deployment
region, retention policy, RPO/RTO, administrative policy, and production approval
are owner decisions. Adapters and fail-closed configuration can be implemented
without inventing those values.

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
| Phase 9 — Interview, networking, growth, analytics          | Defense map, STAR stories, interview prep, consent-based CRM, grounded growth insights/reviews, non-causal analytics               | Phases 3, 8 | New generated stories revalidate claim/evidence; privacy/accessibility tests; analytics is non-causal  |
| Phase 10 — Commercial, admin, hardening, release            | Entitlements/billing, least-privilege admin, deletion/export/audit, limits, load/security, backup/restore, deployment              | Phases 0–9  | No open critical security issues; idempotent webhooks; deletion and restore tested; full CI/build pass |

Detailed checkboxes live in `docs/implementation-checklist.md`.

## Repository structure normalization — 2026-07-27

Status: implementation and all applicable local verification are complete in an
isolated `origin/main` worktree. Draft PR #37 publishes code commit `bf8076e`, and
hosted CI run `30235591776` passed all 14 GitHub Actions jobs plus GitGuardian.
The normalization gate is closed; the PR remains draft and unmerged.

Scope boundary:

- Preserved the accepted monorepo and modular-backend topology. No domain rule,
  API endpoint or payload shape, migration, task name, broker payload, queue,
  production topology, or deployment behavior changed.
- Moved every flat FastAPI feature adapter into
  `rezumi_api/modules/<bounded_context>` and retained only concrete
  cross-cutting HTTP delivery files at the package root.
- Split the monolithic Celery registration file into Career Analytics, Career
  Record, Networking, Resume Builder, Resume Health, and health task modules.
  All 17 registered task names, result shapes, queues, identifier-only payloads,
  retries, fencing, reconciliation, and cleanup semantics are preserved.
- Added executable layout regression checks plus a cross-platform local command
  layer for full/backend/dependency stacks, host hot reload, surface rebuilds,
  status, logs, smoke probes, safe shutdown, and focused tests.
- Corrected the POSIX isolated-E2E default migration head from stale
  `20260726_0011` to the executable single head `20260726_0013`, matching the API
  workflow, PowerShell runner, migration graph, and migration tests.
- Regenerated the official OpenAPI and TypeScript artifacts because moving
  Pydantic classes changes module-qualified component identifiers for otherwise
  duplicate schema names. Endpoints, fields, formats, requiredness, and payload
  shapes are unchanged; contract drift checks are green.
- The newly unblocked browser gate exposed inherited UI-redesign drift and the
  Phase 7 frontend dependency recorded above. The narrow closure aligns
  accessible E2E assertions with current product labels and grounded outcomes,
  confirms required name/skill facts in journey setup, and makes Resume Builder
  poll the existing owner-scoped `GET /api/v1/exports/{export_id}` resource.
  Pending/rendering/retry states are now displayed truthfully; download remains
  disabled until the server returns `verified`; polling is cancellable and
  bounded to 60 seconds. No safety or fidelity rule was weakened.

Verification evidence:

- Frozen setup: `pnpm install --frozen-lockfile` and
  `uv sync --frozen --all-packages --all-groups` pass.
- Structure/local commands: `node --check scripts/local.mjs`,
  `node scripts/local.mjs --help`, `node --check scripts/check-repository.mjs`,
  and `node scripts/check-repository.mjs` pass.
- Python delivery/backend: API Ruff and mypy pass across 73 source files; worker
  Ruff and mypy pass across 20 source files; API tests pass 145/145; worker tests
  pass 89/89; backend architecture/unit tests pass 447/447.
- Repository gates: `pnpm format:check`, `pnpm lint`, `pnpm typecheck`, and
  `pnpm test` pass. The final JavaScript test gate includes contracts 3/3,
  frontend-boundary tests 4/4, UI 12/12, web 164/164, and edge 2/2. GNU Make is
  unavailable on this Windows host, so these are the documented PowerShell
  equivalents of the required Make targets.
- Contracts/build: `pnpm contracts:check`, API/worker Python format checks,
  `pnpm build`, and the final 49-route `pnpm --filter @rezumi/web build` pass.
- Local infrastructure: `docker compose config --quiet`, `pnpm local:status`,
  and `pnpm local:smoke` pass against the restored primary stack.
- Isolated Phase 9 verifier: exact head `20260726_0013`; downgrade to the Phase 8
  boundary and forward repair pass; 42/42 PostgreSQL integration tests pass with
  nine known SQLAlchemy cycle warnings; API/worker/scheduler/web/edge health and
  PostgreSQL stop/start recovery pass; Playwright passes all 12 executed desktop
  and mobile journeys with six intentional mobile skips; all isolated state is
  removed afterward.
- Local `bash -n tests/e2e/run-compose.sh` remains unavailable because this host
  has the WSL launcher but no Linux `/bin/bash`; it is not represented as a local
  shell-syntax pass. Hosted Linux CI executed the POSIX runner successfully in
  every isolated E2E job in run `30235591776`.
- Hosted CI: PR #37 code commit `bf8076e` passed API, worker, web/contracts,
  supply-chain, browser smoke, containers, Resume Health, Career Record, Role
  Explorer, Job Match, Change Studio, Resume Builder, application workspace, and
  Phase 9 career-workspace jobs; GitGuardian also passed.

Residual risks and next step:

- PR #37 remains a draft. Review, merge, and any deployment are separate explicit
  actions; no production environment changed in this phase.
- Normal local commands never delete volumes. The explicitly destructive
  `make reset-db` remains separate and unchanged.
- Host API/worker modes use loopback endpoints derived from `.env`; full-stack
  parity remains the isolated container gate recorded above.
- The initial isolated build hit a full system drive. No Docker data was deleted;
  3.14 GB of installer/temp traces was moved recoverably to
  `.data/recovery-trash/20260727-docker-recovery`, Docker was restarted, and the
  primary stack was restored and re-probed healthy.

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

| ID  | Risk                                                             | Likelihood / impact | Mitigation and gate                                                                                                                                                                                                                     | Earliest owner phase   |
| --- | ---------------------------------------------------------------- | ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| R1  | Cross-tenant data exposure through IDOR or object keys           | Medium / Critical   | Ownership-scoped queries, policy tests, private buckets, audit events                                                                                                                                                                   | 1 and every data phase |
| R2  | Malicious or resource-exhausting documents                       | High / Critical     | Signature/limit checks, scanning, isolated no-network worker, time/memory/CPU caps, hostile fixtures                                                                                                                                    | 2                      |
| R3  | AI fabricates or is redirected by document instructions          | High / Critical     | Untrusted-content delimiters, strict schemas, evidence ledger, deterministic grounding, adversarial tests                                                                                                                               | 5–6                    |
| R4  | Score or preparation labels mislead users                        | Medium / High       | Canonical disclaimer, deterministic versioned formulas, explanations, no probability language; Career Health and Promotion Readiness remain internal, non-employer signals                                                              | 2, 4, 5, 9             |
| R5  | PDF/DOCX looks correct but parses badly                          | High / High         | Constrained templates, searchable text, round-trip verification and blocking critical failures                                                                                                                                          | 7                      |
| R6  | Dependency/toolchain churn breaks the greenfield baseline        | Medium / Medium     | Conservative pins, lockfiles, CI cache keys, scheduled upgrades in small changes                                                                                                                                                        | 0 onward               |
| R7  | Queue retry duplicates work or cost                              | Medium / High       | Idempotency records, bounded retries/timeouts, job state machine, budgets and dead letters                                                                                                                                              | 2 onward               |
| R8  | Sensitive content leaks through logs/telemetry/providers         | Medium / Critical   | Data classification, default redaction, payload-free telemetry, provider minimization and consent                                                                                                                                       | 0 onward               |
| R9  | Local Compose health hides production gaps                       | High / High         | Separate readiness, production threat review, load/restore/failure tests, protected deploy                                                                                                                                              | 10                     |
| R10 | Broad roadmap produces unfinished horizontal scaffolding         | High / Medium       | One vertical phase at a time, dependency gates, no completion on placeholders                                                                                                                                                           | Every phase            |
| R11 | Public demo is mistaken for functional analysis                  | Medium / Medium     | Isolate it at `/demo/dashboard`, retain the fictional-preview label, and keep it free of upload/score claims or account persistence                                                                                                     | 0–1                    |
| R12 | Retention/deletion becomes inconsistent across stores            | Medium / High       | Data inventory, deletion tombstones/jobs, object/vector/backup policy and tests per entity                                                                                                                                              | 1 onward               |
| R13 | Generated contracts drift from implemented OpenAPI               | Medium / High       | FastAPI remains authoritative; pin normalized export/client generation and fail CI on either drift                                                                                                                                      | 0 onward               |
| R14 | Hosted CI and local behavior diverge after architecture changes  | Low / Medium        | Runs 29360385761, 29367040183, 29378312134, 29657932938, 30119088488, 30126993025, and 30128304892 verify the merged predecessor through Phase 8; retain clean contract-output, container, migration, browser, and supply-chain gates   | 0 onward               |
| R15 | Upstream runtime findings do not all have supported stable fixes | Low / High          | CPython 3.13.14 findings `CVE-2025-15366`, `CVE-2025-15367`, and `CVE-2026-12003` are medium, have fixes only in Python 3.15 prereleases, and are nonblocking under the documented policy; monitor stable releases and refresh promptly | 0–1                    |
| R16 | Workspace/migration move regresses runtime or existing databases | Medium / High       | One root lock, preserved revision IDs, fresh/existing upgrade tests, root-context image builds, and direct runtime Alembic verification                                                                                                 | 0                      |
| R17 | Contact consent is misunderstood or withdrawn data is retained   | Medium / Critical   | Purpose-specific append-only attestations, server-owned/database-allowlisted policy IDs, no scraping/import, terminal withdrawal, irreversible PII/content redaction, bounded local reminders, and cross-owner/redaction tests          | 9                      |
| R18 | Analytics cohorts or timezones create misleading comparisons     | Medium / High       | Validated IANA zones, versioned cohort/timestamp/suppression definitions, exact cohort reuse, stale-source rejection, small-cohort suppression, and permanent correlation-only language                                                 | 9                      |

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

After this repository-structure normalization and its narrow browser-gate closure
are raised as a draft PR, the next separate implementation phase is Phase 10B
commercial and billing. Coach/Organization tenancy, durable workflows,
privacy/admin surfaces, and observability, performance, recovery, and protected
release engineering follow in the documented PR order. The POSIX migration-head
correction and web journey repairs are included here because the newly unblocked
full-stack gate proved they directly prevent hosted verification; the changes do
not expand Phase 10 product scope.

Publishing this review branch is part of the requested phase workflow; no PR is
merged and no production deployment occurs without explicit later approval.
