# CareerOS implementation checklist

Status: living delivery checklist  
Last reviewed: 2026-07-24

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

Dependencies: Phase 0 green. Current status: complete. The consolidated local gate
and hosted CI run `29367040183` passed all eight checks against Phase 1 evidence
commit `baab8f7`.

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
- [x] Implement resumable/skippable onboarding through account/guest choice,
      upload handoff, parsed review handoff, role/preferences, and dashboard; defer
      actual upload processing to Phase 2 without fake completion.
- [x] Build Settings skeleton for profile/account/sessions/consent with real state.
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
status: complete; local gates and hosted run `29378312134` pass.

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
      tmpfs path, and cleanup on normal/error exits. The current parser timeout
      cannot kill its `asyncio.to_thread` thread; Celery/container limits mitigate
      it, and per-parser subprocess isolation remains a documented hardening gap.
- [x] Guarded local PDF/DOCX extraction produces plain text, ordered blocks,
      source spans, confidence, parser warnings, authoritative PDF page count, and
      image-only detection behind extractor/OCR/scanner/storage ports. DOCX has only
      a nominal local page value because no renderer is present. OCR is a disabled
      optional port, so image-only input returns insufficient data.
- [x] The parser creates canonical sections/blocks as immutable revision 1.
      Optimistic `If-Match` correction creates a successor snapshot, retains the
      extracted original and spans, rejects an all-no-op update, and emits an audit
      event. The API applies separate correction/analysis rate classes; the domain
      caps canonical revisions and analysis history per document. Resume mutation
      headers constrain `Idempotency-Key` to 8-128 `[A-Za-z0-9._:-]` characters and
      `If-Match` to a quoted positive `int4` value no greater than `2147483647`.
- [x] Parse, analyze, and delete jobs use owner-scoped state, request hashes,
      idempotency, progress, cancellation, bounded retries, dead letter, safe
      errors, trace IDs, allowlisted Celery payloads, per-invocation fencing, and a
      lease longer than the worker hard timeout. Busy delivery retries, transactional
      outbox dispatch, storage compensation, and retention cleanup all have durable,
      bounded attempt/backoff/dead-letter state. A scheduled database-only reconciler
      fences and requeues or dead-letters stale work within separate processing and
      recovery budgets. Parse/analyze cancellation is cooperative; accepted deletion
      is deliberately noncancellable.
- [x] Resume Health `resume-health/1.0.0` / `resume-health-default/1` uses the
      published fixed-point feature/component table, immutable snapshot binding,
      persisted `resume-health-features/1` values and weighted contributions, feature
      hash, exact golden expectations, findings, and no numeric value for image-only/
      sparse input.
- [x] Account and one-document/24-hour guest web flows implement direct upload,
      real progress/cancel, processing polling, empty/loading/success/error,
      plain-text/reading-order review, source-preserving correction, analysis,
      report, explicit consented account claim, and durable deletion. Same-page
      ambiguous transfer/finalize retry reuses in-memory intent/idempotency state;
      reload recovery and resumable file transfer are not implemented.
- [x] Reports show the canonical score disclaimer, components, findings, parser
      warnings, stored measured values, and exact feature score/weight/contribution
      details in keyboard-operable, color-independent disclosures; they never claim
      an employer ATS score, hiring probability, or guarantee.
- [x] Focused unit/component/API/worker/integration/E2E coverage exists for the
      implemented fixture and threat matrix. The full format/lint/type/build,
      migration round-trip, real PostgreSQL/Redis/MinIO/ClamAV, desktop/mobile
      Playwright, container-policy, and separate security-scan gates pass; hosted CI
      run `29378312134` passes all corresponding jobs.

Exit: supported fixtures parse and can be corrected; scores reproduce/explain;
malformed/hostile input fails safely; guest retention and user ownership hold.

Closeout evidence and residual limitations are recorded in `PLANS.md`.

## Phase 3 — Career Profile, Evidence Vault, and Achievement Inbox

Dependencies: Phase 1 ownership; Phase 2 canonical/source-span model. Current
status: locally complete and hosted verified. The consolidated
`scripts/verify-phase3.ps1` gate passed on 2026-07-19.

- [x] Add career profile, experience/education/project/skill/credential/etc.
      entities with ownership, constraints, source provenance, and concurrency.
- [x] Implement profile CRUD, timeline/list, accessible reorder, promotion and
      concurrent-role grouping, conflict detection, and neutral gap display.
- [x] Import/correction proposes profile changes rather than overwriting truth.
- [x] Add evidence item/source/attachment/skill/metric/link models and audited
      Verified/Confirmed/Supported/Inferred/Unsupported transition rules.
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

- [x] Implement structured editor for fields/sections/bullets, accessible reorder,
      evidence-backed additions, bounded typography/layout, autosave, page/plain-text/
      recruiter previews, version comparison, and restore.
- [x] Implement five accessible ATS-friendly single-column-first templates without
      essential text boxes/header/footer/icon-only content; searchable predictable text.
- [x] Add idempotent isolated PDF/DOCX/text/JSON render jobs pinned to immutable
      versions, with private objects, hashes, status, timeout/retry/dead letter.
- [x] Parse PDF/DOCX outputs again and compare all critical entities/bullets/order,
      searchability, duplicates/omissions, reading order, and claim grounding.
- [x] Store/show verification report; block critical failures and clearly warn on
      allowed noncritical failures before download.
- [x] Provide short-lived ownership-checked download intents and complete deletion.
- [x] Test all templates at one/two pages, supported fonts/layouts, round-trip
      goldens, renderer isolation/injection, cross-user download, failure blocking,
      immutable restore/history, keyboard/mobile approval, and accessibility.

Exit: output is searchable and critical fields/claims survive round trip; unsafe
or broken exports cannot masquerade as verified.

Phase 7 implementation note: the vertical slice persists durable export job
status, attempts, retry/dead-letter fields, hashes, object keys, and verification
reports while executing the local deterministic render/verify step immediately in
the application service. Moving that work to a Celery task is a scale/isolation
hardening step, not a different product policy.

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
passed; PR #21 workflow run `30126993025` passed every required hosted job at
head `645536b`.
Phase 9 is the next product phase.

## Phase 9 — Interview Prep, Networking, Career Growth, and Analytics

Dependencies: Phases 3 and 8.

- [ ] Build Resume Defense Map and STAR library linking claim/evidence,
      situation/task/action/result, personal contribution, metric explanation,
      follow-up questions, and confidence; warn on undefended strong claims.
- [ ] Add role-specific question bank, mock session, notes/reflection, and grounded
      follow-up generator.
- [ ] Add consent-based contacts/organizations/stages, interactions, referrals,
      reminders, tags/templates/search/filter; never scrape private contacts.
- [ ] Add goals, achievements/skill evidence, promotion/internal mobility,
      review/learning/certification, quarterly review, annual refresh, and deterministic
      Career Health methodology.
- [ ] Add application/interview/offer/rate/role/industry/source/version/readiness/
      achievement analytics with windows, cohort safeguards, and correlation-only text.
- [ ] Test claim/story grounding, sensitive note/contact ownership and consent,
      reminder idempotency, score goldens, aggregation isolation, small cohorts,
      non-causal language, and accessible charts/tables/workflows.

Exit: every story links evidence/claims; contact consent holds; analytics are
privacy-safe, reproducible, and never causal or predictive.

## Phase 10 — Billing, Admin, Security Hardening, and Production Release

Dependencies: all product phases and production/legal decisions.

- [ ] Store Free/Sprint/Pro/Coach plan entitlements/quotas centrally; no scattered
      prices. Implement billing adapter, checkout/portal, signed raw webhook validation,
      event idempotency/order/state, reconciliation, and test provider.
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
