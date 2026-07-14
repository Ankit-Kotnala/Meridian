# CareerOS implementation checklist

Status: living delivery checklist  
Last reviewed: 2026-07-15

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
- [x] Create `apps/web` with Next.js 16.2.10, React 19.2.7, strict TypeScript
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

Dependencies: Phase 0 green. Current status: implemented and locally verified;
hosted CI is the final closeout gate.

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

Dependencies: Phase 1 identity/ownership; Phase 0 object/queue health.

- [ ] Add owned source-document, processing-job, canonical resume, analysis,
      score-component, and finding models/migrations with state constraints.
- [ ] Implement private upload intent/finalize flow, signature/MIME/size/page/
      expansion validation, randomized object key, quarantine, deletion, and audit.
- [ ] Integrate malware interface/local adapter; production-required scan failure
      quarantines/fails closed. Reject macros/unsupported/encrypted inputs safely.
- [ ] Run parsing in a no-execution, no-unnecessary-network, CPU/memory/PID/time-
      limited worker with randomized temporary paths and cleanup.
- [ ] Implement local PDF/DOCX text extraction, layout analysis, image-only
      detection, optional OCR interface, and parser provider abstraction.
- [ ] Produce canonical sections/entities/bullets with confidence and source spans;
      allow user correction without mutating original source.
- [ ] Implement idempotent async scan/parse/analyze status, progress, cancellation,
      bounded retries, dead letters, trace, and safe errors.
- [ ] Finalize versioned deterministic Resume Health features/formula and golden
      explanations under `docs/scoring-methodology.md`.
- [ ] Build registered and limited short-retention guest flows, report components,
      issues/quick wins/section feedback, plain-text and reading-order previews,
      parser warnings, and correction/save flow.
- [ ] Show canonical score disclaimer and accessible text summaries; no employer
      ATS/hiring-guarantee language.
- [ ] Test all document fixtures, cross-user object/job/status/deletion access,
      parser disagreement, determinism/rounding/missing data, malformed/polyglot/wrong
      extension/oversize/bomb/path/malware/timeout, cleanup, and keyboard workflow.

Exit: supported fixtures parse and can be corrected; scores reproduce/explain;
malformed/hostile input fails safely; guest retention and user ownership hold.

## Phase 3 — Career Profile, Evidence Vault, and Achievement Inbox

Dependencies: Phase 1 ownership; Phase 2 canonical/source-span model.

- [ ] Add career profile, experience/education/project/skill/credential/etc.
      entities with ownership, constraints, source provenance, and concurrency.
- [ ] Implement profile CRUD, timeline/list, accessible reorder, promotion and
      concurrent-role grouping, conflict detection, and neutral gap display.
- [ ] Import/correction proposes profile changes rather than overwriting truth.
- [ ] Add evidence item/source/attachment/skill/metric/link models and audited
      Verified/Confirmed/Supported/Inferred/Unsupported transition rules.
- [ ] Implement evidence CRUD/confirm/archive, private attachments, experience/
      skill/requirement links, and downstream usage view.
- [ ] Enforce generation-eligibility query boundaries; unsupported/inferred/
      conflicted/unauthorized evidence cannot be used as fact input.
- [ ] Implement Achievement Inbox quick add, guided neutral questions, draft,
      metric details, employer/project association, reminders, timeline, and explicit
      conversion to confirmed evidence.
- [ ] Detect date/title/metric/entity conflicts without silently resolving them.
- [ ] Test ownership, state transitions, source-span integrity, attachment access/
      deletion, numeric confirmation, concurrency, conflict/audit, and accessible CRUD.

Exit: users maintain career data independently of a resume; all evidence has
ownership/provenance; unsupported evidence is excluded by tested domain policy.

## Phase 4 — Role Explorer and Role Readiness

Dependencies: Phase 3 profile/evidence and Phase 0 provider/config foundations.

- [ ] Select/license and seed a versioned role taxonomy; add provider interface,
      definitions, competencies, saved roles, and readiness history.
- [ ] Implement search by title/seniority/industry/location/company type/domain,
      save/delete, and compare two or three roles.
- [ ] Finalize deterministic Role Readiness weights/features and skill states;
      store formula/taxonomy/profile/evidence snapshots.
- [ ] Show competency/responsibility/seniority/leadership/domain/technical/business/
      education/evidence components, strengths, gaps, unknowns, transferable/adjacent
      states, evidence links, questions, transitions, and next actions.
- [ ] Never label readiness as a hiring probability; show score disclaimer and
      accessible summaries.
- [ ] Test taxonomy versioning, ownership/history, evidence relevance, unknown/
      not-applicable, determinism/goldens, comparison, and accessibility.

Exit: role comparison works without job text and every score/gap is reproducible,
explained, and linked to evidence or an explicit unknown/missing state.

## Phase 5 — Job Match, Requirement Matrix, and Opportunity Prioritizer

Dependencies: Phases 3–4; URL-import security boundary.

- [ ] Add owned job/source/requirement/match/analysis/opportunity models with
      immutable source text/spans and versions.
- [ ] Implement paste/manual/saved imports and `JobImportProvider`.
- [ ] Implement HTTP(S)-only URL fetch with normalized URL, every-resolution and
      redirect SSRF checks, public-network enforcement, DNS rebinding/IPv4/IPv6
      handling, TLS hostname verification, no scripts/cookies, content sanitization,
      and time/redirect/decompressed-byte/content limits.
- [ ] Extract explicit metadata and requirements with original spans,
      normalized/type/importance/mandatory-preferred/confidence; user can correct them.
- [ ] Match each requirement to eligible evidence as Strong/Partial/Transferable/
      Unknown/Missing/Not Applicable; show full accessible matrix and actions.
- [ ] Finalize deterministic Application Readiness components/credits and display
      mandatory gaps separately.
- [ ] Implement explainable Opportunity Priority using user preferences, deadline,
      effort, and contacts; never predict hire/no-hire.
- [ ] Test cross-user data, source-span round trip, SSRF matrix/sanitizer/limits,
      injected job instructions, model-candidate schema, hard-gap visibility,
      determinism/goldens, user correction, and accessibility.

Exit: every requirement traces to source; every match traces to authorized evidence
or explicit missing/unknown; no model number becomes a score; SSRF tests pass.

## Phase 6 — Change Studio and Truth-Locked AI

Dependencies: Phase 3 eligible evidence, Phase 5 source-spanned requirements,
deterministic scoring.

- [ ] Implement environment-selected AI gateway, production adapter, deterministic
      fake, timeouts/retries/circuit breaker, idempotency, rate/concurrency/cost budgets,
      usage tracking, and provider kill switch.
- [ ] Build minimal-data prompts that separate hostile document text and safely
      handle Unicode controls; no broad tools or raw prompt logging.
- [ ] Validate strict operation/claim/question schemas with bounded fields and
      reject malformed/unknown output.
- [ ] Implement deterministic claim ledger and grounding checks for authorization,
      evidence state/entailment, entities/dates, numbers/units/period/attribution,
      technologies/credentials, contribution/causality, and consistency.
- [ ] Add typed change sets/operations, stable targets, before/after word diff,
      reason/evidence/requirement/risk/confirmation, and deterministic expected-score
      simulation.
- [ ] Implement accept/reject/edit/alternatives/tone/length/preserve/lock,
      policy-safe batch, undo/redo, clarifying questions, and immutable versions.
- [ ] Revalidate user edits; unsupported content never receives a verified state or
      an accept-able prohibited operation.
- [ ] Pass structured fuzz, cross-tenant evidence, unsupported fact/number,
      ownership/leadership/causality drift, prompt injection, sink injection, timeout/
      retry/idempotency/budget, user-control, immutable history, and accessibility tests.

Exit: all suggestions are provenance-visible; unsupported claims/numbers are
blocked; material changes require user control; adversarial suite is green.

## Phase 7 — Resume Builder, Export, and Round-Trip Verification

Dependencies: Phases 2 and 6.

- [ ] Implement structured editor for fields/sections/bullets, accessible reorder,
      evidence-backed additions, bounded typography/layout, autosave, page/plain-text/
      recruiter previews, version comparison, and restore.
- [ ] Implement five accessible ATS-friendly single-column-first templates without
      essential text boxes/header/footer/icon-only content; searchable predictable text.
- [ ] Add idempotent isolated PDF/DOCX/text/JSON render jobs pinned to immutable
      versions, with private objects, hashes, status, timeout/retry/dead letter.
- [ ] Parse PDF/DOCX outputs again and compare all critical entities/bullets/order,
      searchability, duplicates/omissions, reading order, and claim grounding.
- [ ] Store/show verification report; block critical failures and clearly warn on
      allowed noncritical failures before download.
- [ ] Provide short-lived ownership-checked download intents and complete deletion.
- [ ] Test all templates at one/two pages, supported fonts/layouts, round-trip
      goldens, renderer isolation/injection, cross-user download, failure blocking,
      immutable restore/history, keyboard/mobile approval, and accessibility.

Exit: output is searchable and critical fields/claims survive round trip; unsafe
or broken exports cannot masquerade as verified.

## Phase 8 — Application Workspace and Application Packs

Dependencies: Phases 5–7.

- [ ] Add applications/stages/events/tasks/documents and exact job/resume/evidence/
      cover-letter version links with ownership/concurrency/audit.
- [ ] Implement accessible Kanban plus non-drag stage controls, table, calendar,
      search/filter/sort, deadlines/follow-ups, contacts, notes, tasks, referrals,
      interviews, outcomes/reasons, and offer information.
- [ ] Generate grounded tailored resume/letter/bio/fit-interest answers, recruiter/
      hiring/referral/LinkedIn/follow-up messages, introduction, and achievements.
- [ ] Run Application Consistency Engine across dates/titles/metrics/claims and
      resume/letter/answer/interview sources; require conflict resolution.
- [ ] Do not add autonomous submission in the first production release.
- [ ] Test stage state machine, concurrent changes, cross-user records/docs,
      version pinning, pack grounding/consistency, idempotency/cost, deletion/audit,
      accessible Kanban/table/calendar, and end-to-end workflow.

Exit: applications pin exact document versions; all generated pack claims remain
grounded and consistent; workflow tests pass.

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
