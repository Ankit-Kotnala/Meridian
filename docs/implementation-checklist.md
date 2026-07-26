# CareerOS implementation checklist

Status: living delivery checklist  
Last reviewed: 2026-07-25

This checklist expands `PLANS.md`. Check an item only when it is implemented in
real application state and its required test passes. An interface, empty route,
mock success response, skipped test, or fictional preview is not a completed
feature.

## Gate applied to every feature

- [ ] Ownership and authorization rules are explicit and tested, including
      anonymous/cross-user/cross-tenant denial where applicable.
- [ ] Inputs, outputs, sizes, states, and transitions are validated server-side.
- [ ] Loading, empty, success, safe error, retry/cancel, and concurrency behavior
      are implemented where relevant.
- [ ] Desktop, tablet, and mobile behavior is usable; the full workflow is keyboard
      accessible and meets WCAG 2.2 AA.
- [ ] Unit and relevant component/integration/e2e/adversarial tests pass.
- [ ] Persistence has an upgrade migration, constraints/indexes, ownership,
      rollback/forward-repair plan, and no unjustified soft deletion.
- [ ] API/OpenAPI/generated contracts and user/developer documentation are updated.
- [ ] Logs and telemetry exclude secrets/raw career content and carry request/
      trace IDs; required audit events are asserted.
- [ ] Provider failure is bounded and safe; deterministic local/fake behavior
      exists when credentials are unavailable.
- [ ] The feature uses real state. Any fixture is isolated, fictional, and labeled.
- [ ] Formatting, lint, type checks, tests, and relevant builds pass in CI/local.
- [ ] `PLANS.md`, threat model, risks, and ADRs are updated as needed.

## Phase 0 — Repository Foundation

Dependencies: none. Current status: complete. The aligned implementation passed
its complete local gate and hosted CI run `29360385761` on commit `9558f33`; the
earlier baseline evidence remains historical.

### Assessment and governance

- [x] Inspect the complete initial workspace and attached brief.
- [x] Record that the initial repository was empty and preserve inspection evidence.
- [x] Record assumptions, specification tensions, selected stack, Phase 0 boundary,
      dependencies, risks, and verification commands.
- [x] Align repository-specific engineering rules in `AGENTS.md` with the shared
      backend, generated-contract, thin-app, and no-empty-scaffolding decisions.
- [x] Align setup/health/quality instructions in `README.md` with the root
      workspaces and rerun requirements.
- [x] Update product, architecture, security, scoring, AI, API, testing, and ADR
      documentation without erasing prior evidence.
- [x] Create the all-phase checklist and progress plan.
- [x] Add repository ownership, dependency-update, contribution templates, and
      explicit secret/private-data/Terraform-state exclusions.

### Workspace and applications

- [x] Pin pnpm 11.13.0/Node 24 and verify the root workspace lockfile.
- [x] Create `apps/web` with Next.js 16.2.11, React 19.2.7, strict TypeScript
      5.9.3, Tailwind 4.3.2, format/lint/type/test/build scripts.
- [x] Create an accessible initial design system and a conspicuously fictional,
      unauthenticated dashboard preview; do not imply real scoring or persistence.
- [x] Implement web `GET /api/health` and a container production start path.
- [x] Create one Python 3.13 root uv workspace and lock containing thin
      `apps/api`, thin `apps/worker`, and shared `packages/backend` members.
- [x] Implement API `GET /health`, `GET /ready`, and `GET /api/v1/meta` with safe
      schemas; readiness checks required dependencies without leaking topology.
- [x] Keep the Celery 5.6.3 worker thin, preserve task
      `careeros.worker.health.ping`, and retain its broker-backed health check.
- [x] Establish real `packages/backend`, generated `packages/contracts`, generic
      `packages/ui`, `packages/design-tokens`, `packages/eslint-config`,
      `packages/typescript-config`, and `packages/test-fixtures` boundaries.
- [x] Move Alembic and shared database/logging primitives to
      `packages/backend`; preserve revision `20260714_0001` and one migration head.
- [x] Add backend forbidden-import tests and frontend module-boundary checks;
      assert both Python deployables depend on backend and worker never imports API.
- [x] Commit normalized OpenAPI and generated TypeScript schema artifacts, expose
      a typed client wrapper, and fail on export or generation drift.
- [x] Leave extension, future product modules/integrations, root system-test
      suites, Terraform, and operations absent until their owning phases.

### Local platform and automation

- [x] Verify `.env.example` contains documented local-only values and no real secret;
      ignore actual environment files.
- [x] Compose PostgreSQL/pgvector, Redis, MinIO, API, worker, and web with explicit
      health checks and dependency ordering.
- [x] Initialize a private MinIO bucket safely and verify object-service readiness.
- [x] Preserve least-privilege runtime users and production-style start commands;
      build Python images from a root context that includes shared backend files.
- [x] Align non-destructive `make setup`, `dev`, `stop`, `format-check`,
      `lint`, `typecheck`, `test`, and `verify` targets.
- [x] Keep `reset-db` explicitly destructive and documented; ensure Phase 0
      `migrate` only enables pgvector and `seed` only prints labeled fictional data
      rather than pretending domain persistence exists.
- [x] Align CI for frozen root installs, architecture and contract drift checks,
      migration verification, format/lint/types/tests, builds, Compose/container
      smoke, and existing security scans.
- [x] Confirm all test runners discover at least one meaningful foundation test;
      zero-test success is not sufficient.

### Exit verification

- [x] `make setup` succeeds through the documented PowerShell equivalent.
- [x] `docker compose config --quiet` succeeds.
- [x] The documented Compose development path starts the platform.
- [x] Web, API, worker, PostgreSQL, Redis, and MinIO report healthy.
- [x] API readiness changes safely when a required dependency is removed.
- [x] Root workspace, architecture, OpenAPI generation/drift, migration, and
      container migration checks pass.
- [x] The documented PowerShell equivalents of `make format-check`, `make lint`,
      `make typecheck`, `make test`, and `make verify` all pass in this working tree.
- [x] Record command results, changed files, remaining risks, and Phase 1 next step
      in `PLANS.md` before marking Phase 0 complete.
- [x] Commit this aligned working tree and obtain a green hosted CI run for that
      exact revision before marking Phase 0 complete.

## Phase 1 — Authentication, Application Shell, and Onboarding

Dependencies: Phase 0 green. Current status: authentication, sessions, and the
application shell are hosted verified. Server-observed onboarding and Settings
closure are locally verified in the current tree; hosted closure evidence is
pending authorization. The historical consolidated gate and hosted CI run
`29367040183` passed all eight checks against Phase 1 evidence commit `baab8f7`.

- [x] Add users/profiles, hashed session/refresh material, OAuth accounts,
      organization/membership extension, consent, and audit models/migrations.
- [x] Implement email registration and enumeration-safe verification/resend.
- [x] Implement Argon2id login, secure HTTP-only cookie session/refresh rotation,
      reuse detection, logout/current/all-session invalidation, and session UI.
- [x] Implement enumeration-safe forgot/reset with short-lived single-use hashed
      tokens; invalidate affected sessions on success.
- [x] Implement Google OAuth adapter with state, nonce, PKCE, exact redirects, and
      safe account linking; deterministic local provider for tests.
- [x] Enforce CSRF, origin/CORS, rate/abuse controls, secure production cookie
      settings, and no browser-readable persistent bearer token.
- [x] Add recent-auth hooks for future sensitive actions and future-compatible MFA
      architecture without pretending MFA exists.
- [x] Build protected responsive AppShell, expanded/collapsed/mobile Sidebar,
      TopBar, active state, command search/notifications placeholders only when honest.
- [x] Convert dashboard from public fictional preview to protected real skeleton;
      retain a separate explicit demo path only if product approves.
- [x] Complete resumable/skippable onboarding through account/guest choice,
      upload, processing, typed parse review, role/preferences, and dashboard.
      Pipeline progress is an owner-scoped server observation; the browser may
      persist intent and explicit skips but cannot submit observed completion.
- [x] Complete Phase 1 Settings for profile, writing/search/locale/timezone
      preferences, sessions, consent, persisted achievement reminders, password
      management, redacted security activity, Google connection state/removal,
      privacy/retention disclosure, and fail-closed billing/export/deletion
      capability presentation. Actual account export/deletion, billing, and
      scheduled delivery remain their later owning workflows.
- [x] Pass anonymous, cross-user, session rotation/replay/fixation, CSRF, OAuth
      collision, rate-limit, audit, keyboard, responsive, and e2e auth journey tests.

Exit: a user can register, verify, log in, manage/rotate sessions, traverse
onboarding, access protected shell, and log out; protected data fails closed.

Evidence: migration `20260715_0002` upgrades, downgrades, and re-upgrades; 28
backend, 34 API, 12 worker, 17 web, 8 UI, 3 contract, and 4 frontend-boundary
tests pass; two real PostgreSQL/Redis integration workflows pass; and the isolated
Playwright workflow passes 9 checks across desktop/mobile with one intentional
desktop-only project exclusion. `scripts/verify-phase1.ps1` is the consolidated
local gate. Exact closeout evidence and residual limitations live in `PLANS.md`.

## Phase 2 — Resume Upload, Parsing, and General Health

Dependencies: Phase 1 identity/ownership; Phase 0 object/queue health. Current
status: secure intake/extraction, typed semantic parsing/review, and Resume
Health v2 are implemented and locally/security verified; hosted CI for the
closure remains pending explicit authorization to publish. Historical run
`29378312134` remains evidence for the original generic-block v1 slice.

- [x] Migration `20260715_0003` adds exactly-one-owner guest sessions, upload
      intents, source documents, derived artifacts, processing jobs/outbox/object
      cleanup, fenced execution leases, immutable canonical snapshots, analyses with
      feature schema/values/component contributions/findings, and redacted resume
      audit events with constraints and ownership indexes.
- [x] Private S3-compatible upload policy/intent/finalize uses exact expected
      media/size, randomized staging and quarantine keys, signature checks,
      account/guest quota, rate limiting, object promotion, durable deletion, and
      audit without returning permanent credentials or a standalone/unsigned object
      key; the staging key appears only inside its short-lived signed URL. Local `web-edge`
      overwrites address headers from its socket peer before the unexposed web BFF
      signs a neutral per-source API rate key; it is never authorization.
- [x] Required ClamAV scanning fails closed. Local PDF/DOCX admission rejects
      wrong-signature, malformed/encrypted/polyglot, macro, traversal, expansion,
      PDF-page/universal-character-limit, malware, unavailable-scanner, and timeout
      cases with safe codes. DOCX is bounded by byte/archive/expansion/character/
      block/artifact limits because `python-docx` cannot provide authoritative
      rendered page counts; layout-aware enforcement remains provider work.
- [x] The worker runs non-root with a read-only filesystem, dropped capabilities,
      no edge network, bounded CPU/memory/PIDs/time, a private randomized `noexec`
      tmpfs path, and cleanup on normal/error exits. Hostile parsing runs in a
      dedicated child process with bounded input/output, timeout termination and
      reaping, POSIX resource limits, and temporary-workspace cleanup.
- [x] Guarded local PDF/DOCX extraction produces plain text, ordered blocks,
      source spans, confidence, parser warnings, authoritative PDF page count, and
      image-only detection behind extractor/OCR/scanner/storage ports. DOCX has only
      a nominal local page value because no renderer is present. OCR is a disabled
      optional port, so image-only input returns insufficient data.
- [x] Retain immutable source sections/blocks and add typed semantic contact,
      experience, education, project, skill, and certification values with exact
      source anchors, explicit review state, date precision, stable IDs, immutable
      successor snapshots, and typed confirm/correct/add/remove/reclassification
      operations.
- [x] Parse, analyze, and delete jobs use owner-scoped state, request hashes,
      idempotency, progress, cancellation, bounded retries, dead letter, safe
      errors, trace IDs, allowlisted Celery payloads, per-invocation fencing, and a
      lease longer than the worker hard timeout. Busy delivery retries, transactional
      outbox dispatch, storage compensation, and retention cleanup all have durable,
      bounded attempt/backoff/dead-letter state. A scheduled database-only reconciler
      fences and requeues or dead-letters stale work within separate processing and
      recovery budgets. Parse/analyze cancellation is cooperative; accepted deletion
      is deliberately noncancellable.
- [x] Resume Health `resume-health/2.0.0` / `resume-health-default/2` uses the
      documented fixed-point feature/component table, immutable snapshot binding,
      persisted `resume-health-features/2` semantic coverage/review/date/breadth
      values and weighted contributions, feature hash, exact golden expectations,
      findings, and no numeric value for image-only/sparse input. Historical v1
      records remain readable under their exact schema.
- [x] Account and one-document/24-hour guest web flows implement direct upload,
      real progress/cancel, processing polling, empty/loading/success/error,
      plain-text/reading-order and typed semantic review, source-preserving
      corrections, explicit no-change confirmation, legacy upgrade, analysis,
      report, explicit consented account claim, and durable deletion. Same-page
      ambiguous transfer/finalize retry reuses in-memory intent/idempotency state;
      reload recovery and resumable file transfer are not implemented.
- [x] Reports show the canonical score disclaimer, components, findings, parser
      warnings, stored measured values, and exact feature score/weight/contribution
      details in keyboard-operable, color-independent disclosures; they never claim
      an employer ATS score, hiring probability, or guarantee.
- [x] Focused unit/component/API/worker/integration/E2E coverage includes the
      one/two-column, PDF/DOCX, image-only, header/footer, table-heavy,
      date-precision/locale, concurrent-role, unusual-font,
      bidirectional-Unicode, long-document, malformed/encrypted/polyglot, macro,
      traversal, expansion, scanner, and killable-timeout matrix. The exact
      implementation-tree and separate security gates pass as recorded in
      `PLANS.md`; hosted closure evidence remains pending authorization and a
      successful PR run.

Exit: supported fixtures parse and can be corrected; scores reproduce/explain;
malformed/hostile input fails safely; guest retention and user ownership hold.

Closeout evidence and residual limitations are recorded in `PLANS.md`.

## Phase 3 — Career Profile, Evidence Vault, and Achievement Inbox

Dependencies: Phase 1 ownership; Phase 2 canonical/source-span model. Current
status: the evidence graph and core Career Record CRUD are hosted verified.
Resume-ready semantic closure is locally verified in the current tree; hosted
closure evidence is pending authorization. The historical
`scripts/verify-phase3.ps1` gate passed on 2026-07-19.

- [x] Complete resume-ready personal/contact facts and career entities with
      ownership, constraints, explicit fact/entity/skill confirmation,
      canonical per-field provenance, concurrency, and explicit
      experience-project relationships alongside the existing achievement and
      evidence graph links.
- [x] Implement profile CRUD, timeline/list, accessible reorder, promotion and
      concurrent-role grouping, conflict detection, and neutral gap display.
- [x] Import/correction proposes profile changes rather than overwriting truth;
      consume the owner-scoped reviewed Phase 2 typed semantic sidecar instead of
      browser-authored generic blocks. Keep legacy generic proposals readable and
      mark their creation route deprecated for v1 compatibility.
- [x] Add evidence item/source/attachment/skill/metric/link models and audited
      Verified/Confirmed/Supported/Inferred/Unsupported transition rules.
- [x] Bind legacy whole-block `Supported` evidence to the immutable original
      statement digest, restrict new exact-source records to statement-only
      scope, and dynamically exclude mismatched legacy scope without rewriting
      history.
- [x] Implement evidence CRUD/confirm/archive, private attachments, experience/
      skill/requirement links, and downstream usage view.
- [x] Enforce generation-eligibility query boundaries; unsupported/inferred/
      conflicted/unauthorized evidence cannot be used as fact input.
- [x] Implement Achievement Inbox quick add, guided neutral questions, draft,
      metric details, employer/project association, reminders, timeline, and explicit
      conversion to confirmed evidence.
- [x] Detect date/title/metric/entity conflicts without silently resolving them.
- [x] Test ownership, state transitions, source-span integrity, attachment access/
      deletion, numeric confirmation, concurrency, conflict/audit, and accessible CRUD.

Exit: users maintain career data independently of a resume; all evidence has
ownership/provenance; unsupported evidence is excluded by tested domain policy.

Evidence: migration `20260715_0004` upgrades, downgrades to `20260715_0003`, and
re-upgrades; 132 backend unit/architecture, 92 API, 63 worker, 81 web, 12 UI, 3
contract, 4 frontend-boundary, 2 web-edge, 11 real dependency integration, and 4
isolated Playwright workflows pass. Two Phase 3 isolated mobile browser projects
are intentionally skipped because the primary Career Record journey is desktop;
shared responsive shell behavior remains covered by inherited auth flows. Exact
closeout evidence and residual limitations live in `PLANS.md`.

The 2026-07-26 closure gate adds 398 backend, 145 API, 84 worker, 163 web,
41 real-dependency integration, and latest-head migration coverage; the exact
`scripts/verify-phase3.ps1` command passed in 336.3 seconds. Hosted closure
evidence remains pending explicit authorization to publish.

## Phase 4 — Role Explorer and Role Readiness

Dependencies: Phase 3 profile/evidence and Phase 0 provider/config foundations.

- [x] Select/license and seed a versioned role taxonomy; add source/version
      metadata, definitions, competencies, saved roles, and readiness history.
- [x] Implement search by title/seniority/industry/location/company type/domain,
      save/delete, and compare two or three roles.
- [x] Finalize deterministic Role Readiness weights/features and skill states;
      store formula/taxonomy/profile/evidence snapshots.
- [x] Show competency/responsibility/seniority/leadership/domain/technical/business/
      education/evidence components, strengths, gaps, unknowns, transferable/adjacent
      states, evidence links, questions, transitions, and next actions.
- [x] Never label readiness as a hiring probability; show score disclaimer and
      accessible summaries.
- [x] Test taxonomy versioning, ownership/history, evidence relevance, unknown/
      not-applicable, determinism/goldens, comparison, and accessibility.

Exit: role comparison works without job text and every score/gap is reproducible,
explained, and linked to evidence or an explicit unknown/missing state.

Evidence: migration `20260719_0005` upgrades from `20260715_0004`, downgrades
back to it, and re-upgrades. Focused backend/API/web/unit/integration/browser
coverage plus the passing consolidated `scripts/verify-phase4.ps1` result from
2026-07-19 are recorded in `PLANS.md`.

## Phase 5 — Job Match, Requirement Matrix, and Opportunity Prioritizer

Dependencies: Phases 3–4; URL-import security boundary.

- [x] Add owned job/source/requirement/match/analysis/opportunity models with
      immutable source text/spans and versions.
- [x] Implement paste/manual/saved imports and `JobImportProvider`.
- [x] Implement HTTP(S)-only URL fetch with normalized URL, every-resolution and
      redirect SSRF checks, public-network enforcement, DNS rebinding/IPv4/IPv6
      handling, TLS hostname verification, no scripts/cookies, content sanitization,
      and time/redirect/decompressed-byte/content limits. Phase 5 does not yet
      pin the TCP socket to the prevalidated address; ADR 0011 records this
      production hardening item.
- [x] Extract explicit metadata and requirements with original spans,
      normalized/type/importance/mandatory-preferred/confidence; user can correct them.
- [x] Match each requirement to eligible evidence as Strong/Partial/Transferable/
      Unknown/Missing/Not Applicable; show full accessible matrix and actions.
- [x] Finalize deterministic Application Readiness components/credits and display
      mandatory gaps separately.
- [x] Implement explainable Opportunity Priority using user preferences, deadline,
      effort, and contacts; never predict hire/no-hire.
- [x] Test cross-user data, source-span round trip, SSRF matrix/sanitizer/limits,
      injected job instructions, model-candidate schema, hard-gap visibility,
      determinism/goldens, user correction, and accessibility.

Exit: every requirement traces to source; every match traces to authorized evidence
or explicit missing/unknown; no model number becomes a score; SSRF tests pass.
Final consolidated gate evidence is recorded in `PLANS.md`.

## Phase 6 — Change Studio and Truth-Locked AI

Dependencies: Phase 3 eligible evidence, Phase 5 source-spanned requirements,
deterministic scoring.

- [x] Implement environment-selected AI gateway, production adapter, deterministic
      provider, timeouts/retries/circuit breaker, idempotency, bounded request/
      response limits, usage tracking, and provider kill switch. Plan-level
      rate/concurrency/cost budgets remain a later entitlement/operations layer.
- [x] Build minimal-data provider payloads that separate hostile document text and safely
      handle Unicode controls; no broad tools or raw prompt logging.
- [x] Validate strict operation/claim/question schemas with bounded fields and
      reject malformed/unknown output.
- [x] Implement deterministic claim ledger and grounding checks for authorization,
      evidence state/entailment, entities/dates, numbers/units/period/attribution,
      technologies/credentials, contribution/causality, and consistency.
- [x] Add typed change sets/operations, stable targets, before/after review,
      reason/evidence/requirement/risk/confirmation, and bounded deterministic
      expected-score-effect estimates for grounded operations.
- [x] Implement accept/reject/edit/alternatives/tone/length/preserve/lock,
      policy-safe batch, undo/redo, clarifying questions, and immutable versions.
- [x] Revalidate user edits; unsupported content never receives a verified state or
      an accept-able prohibited operation.
- [x] Pass structured/adversarial, cross-tenant evidence, unsupported fact/number,
      ownership/leadership/causality drift, prompt injection, sink injection, timeout/
      retry/idempotency, user-control, immutable history, and accessibility tests.

Exit: all suggestions are provenance-visible; unsupported claims/numbers are
blocked; material changes require user control; adversarial suite is green.

## Phase 7 — Resume Builder, Export, and Round-Trip Verification

Dependencies: Phases 2 and 6.

- [~] Complete structured field/section/bullet CRUD, accessible reorder,
  evidence-backed additions, bounded typography/layout, conflict-safe autosave,
  page/plain-text/recruiter previews, semantic version comparison, and restore.
  The backend now exposes additive source/layout/fact contracts; frontend
  feature implementation remains outside this non-frontend closure.
- [x] Provide five distinct accessible ATS-friendly single-column-first templates
      without essential text boxes/header/footer/icon-only content.
- [x] Move idempotent PDF/DOCX/text/JSON rendering and verification to a durable
      isolated worker with outbox dispatch, leases, bounded retries, dead letter,
      and cleanup.
- [x] Parse outputs again and make critical entity/bullet occurrence counts,
      duplicates/omissions, reading order, searchability, and claim grounding
      release-blocking through one canonical cross-format fidelity manifest.
- [x] Store/show verification report; block critical failures and clearly warn on
      allowed noncritical failures before download.
- [x] Provide short-lived ownership-checked download intents and complete deletion.
- [~] Complete one/two-page coverage for every distinct template, supported
  fonts/layouts, occurrence/read-order goldens, renderer isolation/injection,
  cross-user download, failure blocking, immutable restore/history,
  keyboard/mobile approval, and accessibility. Backend renderer, grounding,
  storage, and owner-scope coverage is complete; new frontend approval work
  remains outside this closure.

Exit: output is searchable and critical fields/claims survive round trip; unsafe
or broken exports cannot masquerade as verified.

Phase 7 closure note: additive migrations `20260726_0012` and
`20260726_0013` preserve the historical vertical-slice schema while adding the
structured editor pins, canonical manifest, operation-typed outbox, fenced
render/cleanup leases, pre-write attempt-object cleanup backstops, bounded
retry/dead-letter recovery, truthful private-object deletion state, and
fail-closed legacy deletion recovery. The historical 2026-07-19 gate remains
evidence only for its original slice; current closure evidence is recorded in
`PLANS.md`.

## Phase 8 — Application Workspace and Application Packs

Dependencies: Phases 5–7.

- [x] Add applications/stages/events/tasks/documents and exact job/resume/
      evidence/requirement revision links with ownership/concurrency/audit.
- [x] Implement accessible Kanban plus non-drag stage controls, table, calendar,
      search/filter/sort, deadlines/follow-ups, contacts, notes, tasks, referrals,
      interviews, outcomes/reasons, and offer information.
- [x] Generate grounded tailored resume/letter/bio/fit-interest answers, recruiter/
      hiring/referral/LinkedIn/follow-up messages, introduction, and achievements.
- [x] Run Application Consistency Engine across dates/titles/metrics/claims and
      resume/letter/answer/interview sources; require conflict resolution.
- [x] Do not add autonomous submission in the first production release.
- [x] Test stage state machine, concurrent changes, cross-user records/docs,
      version pinning, pack grounding/consistency, idempotency/cost, deletion/audit,
      accessible Kanban/table/calendar, and end-to-end workflow.

Exit: applications pin exact document versions; all generated pack claims remain
grounded and consistent; workflow tests pass.

Phase 8 implementation note: application sources pin the exact job
version/source hash and immutable resume version, revalidate its per-claim hash
ledger, and copy evidence revision numbers/statement hashes; incomplete legacy
source ledgers remain readable as explicitly unpinned history but fail closed as
Resume Builder/Application Workspace generation input.
List and child reads are cursor-paginated, detail panels load on demand, and
application/task writes use optimistic concurrency. Application, task, note,
event, and pack creates reuse one stable idempotency key for an unchanged user
intent, including when event time is omitted. Closeout coverage also verifies the
immutable `20260719_0007` migration, legacy refusal, database enum parity, an
atomic resume-change transaction, non-ASCII cursor rejection, and conflict-safe
UI reload.

Phase 8 local closeout passed on 2026-07-24 for implementation revision
`964cd9c`: `scripts/verify-phase8.ps1` exited 0 with `206` backend, `104` API,
and `121/121` web tests across 35 files, a 39-route production build, migration
rollback/forward repair, integration/worker/container probes, and the complete
desktop/mobile Application Workspace workflow. The separate security scan also
passed; PR #21 workflow runs `30126993025` and `30128304892` passed every
required hosted job.
Phase 9 is complete and hosted verified. PR #22 workflow run `30161489265`
passed every required job at implementation/merge head `1454792`; exact evidence
is recorded in `PLANS.md`.

## Phase 9 — Interview Prep, Networking, Career Growth, and Analytics

Dependencies: Phases 3 and 8.

- [x] Build Resume Defense Map and STAR library linking claim/evidence,
      situation/task/action/result, personal contribution, metric explanation,
      follow-up questions, and confidence; warn on undefended strong claims.
- [x] Add role-specific question bank, mock session, notes/reflection, and grounded
      follow-up generator; revalidate exact canonical evidence before every new
      generated bank or follow-up while preserving immutable idempotent replay.
- [x] Add consent-based contacts/organizations/stages, interactions, referrals,
      reminders, tags/templates/search/filter; never scrape private contacts; make
      collection/storage withdrawal a parent-and-child tombstone while preserving
      only the permitted history for outreach-only withdrawal.
- [x] Make consent policy identifiers server-owned wire enums with application
      validation and a database allowlist so retained ledger rows cannot carry
      user-authored PII.
- [x] Add goals, achievements/skill evidence, promotion/internal mobility,
      review/learning/certification, quarterly review, annual refresh, and deterministic
      Career Health methodology.
- [x] Add application/interview/offer/rate/role/industry/source/version/readiness/
      achievement analytics with windows, cohort safeguards, and correlation-only text.
- [x] Derive current eligible achievement history and skill-evidence coverage
      from Career Record without persisting a second factual authority.
- [x] Add a six-check non-predictive Promotion Readiness report and require
      eligible evidence before completing certifications, annual refreshes, or
      finalizing factual reviews.
- [x] Add IANA-timezone application cohorts, versioned metric/cohort/timestamp/
      suppression definitions, requirement-coverage trends, and observed outcomes
      by exact immutable resume version; restrict event buckets to the selected
      application cohort and bind freshness to the exact windowed supplemental point
      set.
- [x] Add migration `20260724_0010`, generated contracts, transactional analytics
      outbox processing, UUID-only worker payloads, local-only reminder
      occurrence/retry/dead-letter processing, and read-only safe execution status.
- [x] Enforce owner/idempotency/parent locks, collection quotas, full contact-child
      redaction, parent PII tombstones, purpose-bound cursors, trace propagation and
      bounded safe reminder retention, exact Growth evidence provenance on every
      link mutation, current-pin insight filtering and review chains, and Career
      Health/Analytics snapshot hash validation. Return typed `429` quota and
      declared `413` body-limit problems.
- [x] Add complete accessible desktop/mobile workflows for all four Phase 9
      workspaces with loading/empty/success/failure/conflict and request-race
      handling.
- [x] Test claim/story grounding, sensitive note/contact ownership and consent,
      reminder idempotency, score goldens, aggregation isolation, small cohorts,
      non-causal language, and accessible charts/tables/workflows.
- [x] Publish the locally and security-verified final tree through hosted CI and
      record the green workflow evidence in `PLANS.md`.

Exit: every ready/generated factual story field links exact eligible
claims/evidence and every new generated artifact revalidates its pins (incomplete
drafts remain explicitly non-ready); contact consent, parent tombstoning, and
purpose-specific redaction hold; Growth factual finalization and live insight
checks remain exact-current and evidence-backed; and analytics are bounded,
privacy-safe, reproducible, timezone-specific, exact-cohort, and never causal or
predictive.

## Repository structure normalization

Dependencies: current merged application baseline and the accepted monorepo ADRs.

- [x] Preserve `apps/web`, `apps/api`, `apps/worker`, and `packages/backend`
      runtime and dependency boundaries; do not flatten the backend.
- [x] Co-locate every FastAPI bounded-context adapter below
      `careeros_api/modules/<bounded_context>` while leaving only concrete
      cross-cutting delivery files at the API root.
- [x] Split Celery registration into bounded-context task modules while
      preserving task names, queues, payloads, retry/fencing behavior, and public
      task imports.
- [x] Add executable structure checks that reject flat API feature adapters and
      a returning monolithic worker task file.
- [x] Add cross-platform full-stack, focused-container, hot-reload, rebuild,
      status, logs, safe shutdown, smoke, and surface-specific test commands.
- [x] Document where frontend, API, worker, backend, contract, and infrastructure
      changes belong and when Docker images require rebuilding.
- [x] Pass format, lint, type, unit, contract, build, Compose, integration, and
      applicable isolated browser gates on the final tree; all applicable local gates
      are green, and PR #37 code commit `bf8076e` passed hosted CI run `30235591776`.

Exit: delivery adapters have one predictable bounded-context address and local
frontend/backend iteration no longer requires hand-composed service commands.
Normalization preserves API payloads, domain rules, tasks, migrations, queues,
and production topology. Official generated component identifiers follow the
relocated schema modules; the narrow browser-gate closure truthfully polls durable
exports and aligns E2E fixtures/assertions without weakening grounding policy.

## Phase 10 — Billing, Admin, Security Hardening, and Production Release

Dependencies: all product phases and production/legal decisions.

- [x] Close the inherited Resume Builder release gaps: durable outbox-backed
      render/verify/cleanup workers with fast `202` acceptance and reload-safe
      polling, distinct constrained layouts, a canonical cross-format fidelity
      manifest, and release-blocking fidelity/grounding checks.
- [x] Replace the preview-only `make seed` behavior with an idempotent,
      explicitly fictional, local-only database/object-store seed spanning
      Phases 1 through 9, guarded before I/O against non-development,
      nonlocal database/object targets, unexpected buckets, and schema drift.
- [x] Store Free/Sprint/Pro/Coach plan entitlements/quotas centrally; no scattered
      prices. Implement billing adapter, checkout/portal, signed raw webhook validation,
      event idempotency/order/state, reconciliation, and test provider.
- [x] Extend the reserved organization layer with server-derived owner/admin/coach/
      member capabilities, non-disclosing durable invitations, minimized rosters,
      and explicit expiring/revocable summary grants; no implicit raw career-data
      access and no synthetic organization for individual accounts.
- [x] Close durable background workflows with phase-owned database state,
      identifier-only task delivery, bounded leases/timeouts/retries/dead-letter,
      reconciliation, redacted telemetry, and live PostgreSQL worker coverage;
      organization invitations now use deterministic replay-safe credentials and
      bounded SMTP composition.
- [ ] Build protected least-privilege admin system/job/dead-letter/safe retry,
      aggregate metrics, plans/flags, taxonomy/templates, redacted errors, and audit;
      no default unrestricted raw documents.
- [ ] Complete data inventory, consent, user export, document/account deletion
      across SQL/object/vector/cache/provider, backup expiry, status/retry, and tests.
- [ ] Finalize rate/abuse/cost limits, security headers/CSP, session/MFA decision,
      audit integrity, scanner/parser sandbox/egress, dependency/container/IaC/SBOM/
      provenance, secret/key rotation, and penetration review.
- [ ] Select production regions/services/queue/object/provider topology and add
      approved ADRs, infrastructure, encrypted backup/PITR, tested restore, RPO/RTO,
      monitoring/alerts/runbooks/on-call, capacity/load/soak/failure testing.
- [ ] Add protected CI/CD environment, manual production approval, migration
      preflight/rollback-forward repair, canary/rollback, and launch checklist.
- [ ] Finalize legal terms/privacy/security/scoring/AI/public pricing content and
      remove or label all demo placeholders; verify no fabricated testimonial.
- [ ] Run full format/lint/type/unit/component/integration/e2e/accessibility/
      responsive/security/migration/container/load/restore suite and production build.

Exit: no open critical security issue; webhooks/deletion/restore are tested;
production build and full CI pass; deployment is protected and manually approved.

## Phase-close record template

Copy into `PLANS.md` when closing a phase:

```markdown
### Phase N evidence — YYYY-MM-DD / revision

- Scope completed:
- Changed files/components:
- Migrations/contracts:
- Commands and exit codes:
- Test results (passed/failed/skipped):
- Security/accessibility evidence:
- Known limitations and residual risks:
- Deferred work (with owner phase):
- Next phase:
```
