# CareerOS testing strategy

Status: Phase 1/3 observed-onboarding, Settings, and resume-ready Career Record
closure locally verified; hosted closure evidence is pending authorization.
Phase 2 semantic closure is locally/security verified; Phase 8 and Phase 9 local,
security, and hosted closeout passed
Last reviewed: 2026-07-26

## Objectives

Testing must prove the product's highest-risk claims, not only produce coverage:

- tenant/user isolation and session safety;
- hostile documents and URL imports fail safely;
- scoring is deterministic, bounded, versioned, and explainable;
- unsupported claims and metrics cannot enter grounded output;
- user approval and immutable history remain intact;
- generated files preserve critical data on round-trip parsing;
- deletion covers all stores according to policy;
- primary workflows work with keyboard, screen reader semantics, mobile, and safe
  failure states;
- local/CI behavior is reproducible without real private data or third-party
  credentials.

No phase is complete when a required test fails, is skipped, is quarantined, or
never runs. A runner reporting zero tests is a configuration failure.

## Test layers

| Layer                  | Purpose                                                                      | Typical tools / boundary                                                             |
| ---------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Static                 | Formatting, lint, strict types, dependency/config/schema checks              | pnpm scripts, ESLint, TypeScript, Ruff, mypy/pyright as selected, OpenAPI validation |
| Unit                   | Pure domain rules, features, state machines, validators, provider adapters   | Vitest and Pytest; no network/time randomness                                        |
| Component              | UI states, semantics, focus, keyboard, responsive variants                   | React Testing Library/Vitest, axe-compatible checks, Storybook where valuable        |
| Contract               | OpenAPI response/request/error/idempotency compatibility and generated types | FastAPI/Pydantic tests, normalized OpenAPI snapshots, typed client compile           |
| Integration            | API + PostgreSQL/Redis/MinIO, worker tasks, migrations, object lifecycle     | Isolated Compose/test containers and Pytest; real dependencies, fake externals       |
| End-to-end             | User-visible journeys and cross-service behavior                             | Playwright on a seeded fictional environment                                         |
| Adversarial/security   | Authorization, upload/SSRF/prompt/sink abuse, sessions, rate/cost            | Dedicated fixtures/test servers/fuzz/property checks; safe isolated malware fixtures |
| Export fidelity        | Renderer output parse/search/read order/grounding                            | Golden structured inputs, PDF/DOCX generation and independent reparse                |
| Performance/resilience | Limits, concurrency, queues, degradation, restore                            | Load/soak/fault tests in non-production isolated environments                        |

Prefer many fast deterministic domain tests, fewer real-dependency integration
tests at trust boundaries, and a focused e2e portfolio for critical journeys.
Do not mock away the boundary a test is meant to prove.

## Environments and isolation

- Unit/component tests run without network and use deterministic clocks, UUIDs,
  providers, and random seeds when outputs matter.
- Integration tests receive a unique database/schema, bucket prefix, Redis
  namespace, and tenant/user fixtures. Parallel workers cannot share mutable state.
- E2E starts from an isolated empty stack and creates unique fictional data, or
  from an explicit fictional seed when a suite requires one. It destroys its
  containers, networks, volumes, and local images. Retries must not hide failure;
  retained traces/screenshots/video must contain only fictional/redacted content.
- External AI, email, OAuth, billing, OCR, taxonomy, and monitoring use
  deterministic fakes by default. Separate opt-in provider contract tests use
  non-production credentials and never gate ordinary contributor tests on secrets.
- Time-dependent retention/session/deadline tests inject a clock rather than sleep.
- Property/fuzz tests record the failing seed and promote regressions to fixtures.
- Tests never use a real person's resume, contact, email, token, or private job
  application. Demo and fixture data is marked fictional.

## Foundation test plan (Phase 0)

### Web

- Render the foundation page/dashboard preview and assert the fictional label,
  canonical product tagline, no real analysis claim, semantic landmarks, keyboard
  focus, and accessible status text.
- Test `GET /api/health` schema/status and production build/start.
- Run strict TypeScript, lint, unit/component, and build.
- Add a Playwright smoke at desktop and mobile widths when the integrated stack is
  available; assert no critical accessibility violation on the main preview.

### API

- Test `/health` remains responsive without dependency work.
- Test `/ready` succeeds with required services and fails safely when a required
  dependency is unavailable; no credential/host/stack trace appears.
- Test `/api/v1/meta` exact safe schema, service/version/environment, and canonical
  internal-score disclaimer.
- Validate OpenAPI generation and unique operation IDs.
- Run formatting, lint, types, unit tests, and import/startup smoke.

### Worker and local services

- Execute/control-ping `careeros.worker.health.ping` through the broker and assert
  deterministic safe response.
- Test worker import/config without contacting unavailable optional providers.
- Validate Compose configuration and health for PostgreSQL/pgvector, Redis, MinIO,
  API, worker, and web; verify startup dependency behavior.
- Verify MinIO bootstrap is idempotent and bucket is not public.
- Inspect images/config for real secrets and unintended development commands.

### Architecture, migrations, and contracts

- Install `apps/api`, `apps/worker`, and `packages/backend` from one frozen root
  uv workspace and assert both deployables depend on the backend.
- Run static negative-fixture architecture tests: backend never imports a
  deployable, worker never imports API, deployables do not own persistence, and
  domain/application layers reject framework or provider SDK imports.
- Run frontend boundary checks that keep route files thin, product behavior under
  `src/modules`, and generic UI in `packages/ui`.
- Export FastAPI OpenAPI deterministically, compare the committed normalized
  artifact, regenerate the TypeScript schema with pinned tooling, compile the
  typed client wrapper, and fail on either form of drift.
- Assert one Alembic head with revision history preserved. Upgrade a fresh
  database, verify the current revision, and exercise the installed container
  migration command without relying on uv in the runtime image.
- Build API and worker from the repository root context and confirm only required
  workspace files enter each runtime image.

### Repository gate

```sh
make setup
docker compose config --quiet
make dev
docker compose ps
make format-check
make lint
make typecheck
make test
make verify
```

Capture exact output/exit status in `PLANS.md`. If a host lacks Docker/Make, CI may
provide additional evidence but the documented setup path remains unverified until
it runs in a supported environment.

The expanded repository gate passes in the current aligned working tree. Phase 0
is closed by hosted CI run `29360385761`; its earlier foundation baseline remains
historical evidence only.

## Identity and onboarding test plan (Phase 1)

- Backend unit and API tests cover registration/verification, enumeration-safe
  recovery, Argon2id settings, session rotation/replay-family revocation, one-use
  tokens, CSRF/origin policy, abuse limits, audit events, owner denial, optimistic
  updates, Google OAuth validation/collision behavior, password rotation,
  all-session invalidation, redacted owner-scoped security activity, fail-closed
  Settings capabilities, and the streamed body cap.
- Two integration tests use isolated real PostgreSQL and Redis. They are selected
  explicitly by the full-stack runner and fail when dependency URLs are absent;
  the fast unit runner does not disguise them as skipped coverage.
- The migration gate exercises `20260714_0001` to `20260715_0002`, downgrade, and
  forward re-upgrade, and verifies the runtime image reports one expected head.
- Web/UI tests cover contract-bound requests, proxy allowlists and failures,
  validation, loading/empty/success/error feedback, session-bound CSRF, refresh
  coalescing, protected navigation, server-observed onboarding, all Settings
  loading/empty/success/error states, unavailable capability disclosure, and
  accessible form primitives.
- The isolated Playwright journey creates a unique fictional user, reads the
  Mailpit verification link, signs in, persists honest Phase 2 onboarding skips,
  reaches the real empty dashboard, exercises keyboard/mobile navigation, creates
  and revokes the exact secondary session, proves its `/me` access fails, logs out,
  and confirms protected-route denial.

The frozen-tree result is 28 backend, 34 API, 12 worker, 17 web, 8 UI, 3 contract,
and 4 boundary tests; both real-dependency integrations pass. Playwright reports 9
passed and 1 intentional desktop-project exclusion for a mobile-only assertion;
the assertion runs in the mobile project, so no required behavior is skipped.
`scripts/verify-phase1.ps1` orchestrates the complete local gate and cleans its
isolated containers, networks, volumes, images, and browser artifacts.

## Resume Health test plan (Phase 2)

- Backend domain tests cover exact owner cardinality, capability hashing and
  constant-time verification, job transitions/cancellation/dead letter,
  per-invocation fencing/lease recovery and stale-writer denial, fixed-point score
  features, v1/v2 persisted feature values/contributions, insufficient-data
  behavior, bounds, determinism, and independently asserted v2 golden score cases.
- Service tests exercise the registered upload/parse/correct/analyze/delete
  workflow, cross-user denial, guest expiry and explicit claim, account/guest
  quotas, consent, scheduled retention deletion, outbox publication failure and
  recovery/dead letter, durable object-cleanup retry/dead letter, busy-delivery
  handling, claim denial during active/retryable work and lost-response replay,
  no-op correction and history caps, infected/unavailable scanner handling,
  retry exhaustion, stale published/lost-retry/expired-lease reconciliation,
  processing/recovery budget exhaustion, and cancellation. In-memory adapters are
  deterministic contract fakes; they do not replace the real-provider
  integration layer.
- Extractor tests use committed fictional one/two-column PDF, DOCX, image-only,
  header/footer, table-heavy, date-locale/concurrent-role, unusual-font,
  bidirectional-control, and long-resume fixtures plus test-generated
  wrong-signature, malformed, encrypted, polyglot, macro, traversal,
  expansion-entry, compression-ratio, and forced-timeout inputs. Tests prove the
  parser child is terminated/reaped and its temporary workspace removed. The
  fixtures and manifest are deterministic and contain no user data.
- Integration tests use a migrated real PostgreSQL database for owner-scoped
  repository/job state, private S3-compatible storage for signed upload/promote/
  download/delete lifecycle, and real ClamAV with an isolated dynamically
  assembled standard test signature. They fail rather than skip when the Phase 2
  runner has not supplied its dependencies.
- API tests cover real policy values, account authentication/owner scope, opaque
  guest cookie scope and CSRF, neutral HMAC-signed per-source pre-auth/guest-upload
  rate keys, invalid/absent production signals, correction/analysis rate classes,
  exact idempotency/`If-Match` bounds, typed semantic operations/no-change
  confirmation/legacy upgrade, cross-owner denial, and score response
  feature-schema/value/contribution/hash/disclaimer behavior. Worker tests cover
  strict queue envelopes, allowlisted task publication, runtime failure mapping,
  parser subprocess isolation, fencing/busy retry, bounded maintenance inputs,
  and secure configuration.
- Web/UI tests cover filename/media/size validation, exact-origin direct upload,
  byte progress and abort, same-page in-memory intent/finalize retry, loading/
  empty/success/error states, processing and deletion semantics, immutable
  typed semantic correction/confirmation/add/remove/reclassification,
  explicit no-change legacy upgrade, insufficient data, stored measured values
  and weighted contribution text equivalents, canonical disclaimer, keyboard
  interaction, and accessible file/progress/tab/dialog/disclosure primitives.
- Playwright extends the registered Mailpit/account journey through real PDF
  upload, parse polling, source-preserving correction, reanalysis, report, and
  dashboard. A separate guest journey covers upload/report, explicit save prompt,
  and durable deletion without silently transferring data.

The consolidated Phase 2 runner builds an isolated stack, migrates to
`20260715_0003`, downgrades to `20260715_0002`, re-upgrades, runs real dependency
integrations, asserts worker policy and anonymous-object denial, proves packaged
API readiness fails closed while PostgreSQL is stopped and recovers after it is
restarted, then runs the desktop/mobile journeys:

```powershell
.\scripts\verify-phase2.ps1
```

The same-revision local suites pass: 280 unit/API checks, 5 real provider
integrations, and Playwright 10 passed with 2 intentional project exclusions and
0 failures. Exact package counts and hosted run `29378312134` are recorded in
`PLANS.md`; that plan remains the completion evidence.

Security regressions additionally assert that local `web-edge` discards spoofed
client-address/hop headers and overwrites them with its socket peer, the web
container has no direct host-published port, identical normalized sources produce
stable BFF signatures, production fails closed without a real signing secret, and
HTTP failure/completion logs use route templates without request payloads or
exception text. An exception-message canary uses normal test-server propagation,
asserts the marker is absent from both logs and the generic no-store response,
and proves the exception is not re-raised. Cloud-load-balancer trusted-hop
behavior remains a deployment test because the local single-hop edge
intentionally does not trust forwarded addresses.
The separate source/dependency/image security gate also scans the pinned
`web-edge` Node Alpine runtime; `verify-phase2.ps1` does not substitute for that
scan.

## Career record and Evidence Vault coverage (Phase 3)

Phase 3 keeps every Phase 2 gate and adds blocking coverage for the decisions in
ADR 0009. The focused suites and isolated stack runner implement the following
coverage; exact closeout results are recorded in `PLANS.md`:

- Domain tests exercise every permitted and forbidden evidence-strength
  transition, keep archive/delete lifecycle separate from strength, prove that a
  client or owner confirmation cannot create `Verified`, and require an explicit
  allowlisted verification-authority decision for that transition.
- Eligibility tests cover factual and numeric use independently. Inferred,
  unsupported, archived, deleted, conflicted, unauthorized, and source-unavailable
  evidence is excluded. Numeric evidence additionally requires confirmed or
  verified value/range, unit/currency, period, precision, attribution, and any
  applicable baseline/comparator.
- Service/repository tests mutate user IDs on profile entities, nested evidence
  links, conflicts, proposals, achievements, attachments, lists, and usage reads.
  Unknown and cross-user identifiers return the same result. Stale `If-Match`,
  incomplete/duplicate reorder sets, concurrent proposal review, and concurrent
  achievement conversion cannot overwrite or duplicate state.
- Provenance tests verify source document/snapshot/revision/block/span bounds and
  digest integrity through the Resume Health application query. Import creates a
  pending proposal only. Deleting the source keeps accepted career truth but makes
  source-only Supported evidence ineligible until it is independently confirmed
  or given another eligible source.
- Conflict tests cover duplicate experience/title/date, legitimate concurrent
  roles and promotion sequences, neutral career gaps, and contradictory entity or
  metric values. Resolution is explicit and audited; no test permits silent
  mutation of a competing record.
- Achievement Inbox tests preserve unanswered neutral questions, reject leading
  or invented metric defaults, validate complete metric dimensions, persist
  reminder preferences, and convert a reviewed draft into one idempotent Confirmed
  evidence record.
- Attachment tests cover signed operation/key/size/type scope, byte signature,
  malformed/archive-limit/malware/scanner-unavailable failures, clean-state access,
  cross-user download denial, idempotent finalize, bounded retry/dead letter, and
  durable private-object cleanup on unlink/delete.
- API/contract tests cover authenticated CSRF, bounded filters and opaque cursor
  pagination, strict unknown-field rejection, safe field problems, `If-Match` and
  idempotency bounds, no public state elevation, generated-contract drift, and
  redacted audit/log output.
- Web component tests cover loading, empty, filtered-empty, success, validation,
  safe failure, rate-limit, and version-conflict recovery states. Timeline and
  list semantics, state versus eligibility labels, provenance, non-drag reorder,
  focus restoration/error summaries, reduced motion, long content, and mobile
  overflow are accessibility gates.
- Full-stack Playwright creates career data without a resume, adds a skill/project/
  experience, captures and confirms evidence, and explicitly converts a completed
  achievement draft into evidence. The Phase 3 primary workflow runs once in the
  desktop Chromium project; the inherited authentication journey continues to
  exercise the shared workspace shell on desktop and mobile. Proposal review,
  private attachment processing, unsupported eligibility, and incomplete drafts
  are covered in API/domain/component/integration suites rather than overstated as
  browser coverage.
- Closure tests load reviewed typed Resume Health semantics through the
  owner-scoped application port, exclude unreviewed/removed fields, require
  essential experience dates, preserve exact field anchors, distinguish
  parser/user-added/owner-edit origins, and validate the canonical value digest
  before returning current provenance. They cover personal facts,
  fact/entity/skill confirmation and edit revocation, explicit
  experience-project relationships, downstream confirmed-only snapshots, and
  legacy generic-proposal compatibility.

The migration gate is fresh bootstrap plus
`20260715_0003 -> 20260715_0004 -> 20260715_0003 -> 20260715_0004`, followed by a
single-head/drift check. Final local counts and exact commands are recorded in
`PLANS.md`; hosted CI evidence is recorded separately when an implementation
revision is published.

The resume-ready closure separately bootstraps the preceding
`20260724_0010` head, upgrades to `20260726_0011`, runs `alembic check`, proves
historical records are not silently confirmed and owner/primary-fact constraints
fail closed, downgrades, and repairs forward. Real PostgreSQL repository tests
round-trip confirmations, facts, provenance, and relationships with owner
isolation and delete cascades. The consolidated Phase 3 runner still executes the
complete predecessor portfolio and latest migration head.

The closure migration test also deliberately removes canonical Phase 9 columns,
foreign keys, unique/check constraints, and indexes to simulate a long-lived
pre-release database. Upgrade backfills deterministic timezone, ordinal, and
trace metadata, rejects conflicting rows instead of deleting them, preserves
Phase 9-owned repairs on downgrade, and finishes with no Alembic drift. On
2026-07-26 the exact cumulative gate passed in 336.3 seconds: 398 backend,
145 API, 84 worker, 163 web, 12 UI, 3 contract, 41 real-dependency integration,
and 4 Playwright tests passed; 2 narrower mobile journeys were intentionally
skipped.

## Role Explorer and readiness coverage (Phase 4)

Phase 4 keeps every Phase 3 gate and adds blocking coverage for ADR 0010:

- Scoring tests cover no-signal insufficient data, deterministic fixed-point
  weights, demonstrated versus listed skills, eligible evidence relevance, state
  ceilings, and explainable required gaps.
- Service tests cover role search/filtering, saved-role create/update/delete,
  stale versions, owner denial, idempotency replay/conflict, snapshot reuse, audit
  events, history, and two-or-three-role comparison.
- Migration tests assert public taxonomy tables are intentionally not user-owned,
  saved roles and analyses are owner-owned, indexes/constraints match the ORM,
  and the graph upgrades from and downgrades to the Phase 3 head.
- Repository integration uses real PostgreSQL to save roles, analyze against an
  owned Career Record snapshot, fetch history, deny cross-user access, and prove
  role-readiness audit rows do not store raw evidence text.
- API tests cover authenticated reads, CSRF mutations, `If-Match`,
  `Idempotency-Key`, owner-scoped not-found behavior, generated response shapes,
  score disclaimer propagation, and comparison query bounds.
- Web tests cover loading, empty, success, failure, saved-role notes, analysis,
  evidence-linked result tables, history, comparison, accessible labels, and
  non-color-only score summaries.
- Full-stack Playwright registers a fictional user, creates and confirms career
  evidence through Phase 3 UI, then saves, annotates, analyzes, and compares roles
  in Role Explorer. The primary Role Explorer journey runs once in desktop
  Chromium; inherited auth/workspace suites continue desktop/mobile coverage.

The consolidated `scripts/verify-phase4.ps1` gate passed on 2026-07-19. It
retains the previous phase gates, verifies migration
`20260715_0004 -> 20260719_0005 -> 20260715_0004 -> 20260719_0005`, runs real
dependency integrations, and exercises the authenticated Role Explorer
save/analyze/compare journey in the isolated stack.

## Job Match and Opportunity Priority coverage (Phase 5)

Phase 5 keeps every Phase 4 gate and adds blocking coverage for ADR 0011:

- Scoring tests cover deterministic job metadata/requirement extraction, source
  spans, eligible evidence links, hard-gap counts, insufficient-data behavior,
  and versioned Application Readiness snapshots.
- Service tests cover job create/import/update/delete ownership, idempotency
  replay/conflict, stale-version rejection, target role lookup through the Role
  Readiness boundary, career snapshot reuse, analysis creation, latest-analysis
  priority calculation, and redacted audit events.
- URL importer tests cover HTTP(S)-only enforcement, blocked loopback/private
  destinations, redirect validation, response-size limits, and HTML
  script/style stripping. Tests must not require external network access.
- Migration tests assert every Phase 5 table is owner-scoped, composite foreign
  keys include `owner_user_id`, and migration `20260719_0006` matches registered
  SQLAlchemy metadata.
- API tests cover authenticated create/analyze/requirements/priority workflow,
  CSRF requirements for mutations, idempotency headers, no raw `sourceText` in
  job responses, scoring disclaimer exposure, and cross-user denial.
- Web component tests cover loading, empty, success, failure, pasted-job save,
  analysis matrix, eligible evidence display, disclaimer display, and priority
  output.
- The Phase 5 Playwright journey registers and verifies a real account, creates
  confirmed fictional career evidence, saves a pasted job posting, analyzes the
  requirement matrix, confirms the evidence link and internal-score disclaimer,
  and calculates opportunity priority.

`scripts/verify-phase5.ps1` passed on 2026-07-19. The isolated stack reported
migration head `20260719_0006`, successful rollback to `20260719_0005` and
forward repair, `13 passed` backend integration tests, and `6 passed, 4 skipped`
Playwright project results for the configured desktop/mobile journey portfolio.

## Change Studio and truth-locked AI coverage (Phase 6)

Phase 6 keeps every Phase 5 gate and adds blocking coverage for ADR 0012 and
`docs/ai-grounding-policy.md`:

- Grounding tests cover strict provider schema parsing, unknown-field rejection,
  unsupported facts, prompt-injection text, unsafe sink content, unauthorized
  evidence/requirement IDs, unconfirmed numeric claims, and deterministic
  conversion of missing facts into clarifying questions.
- Service tests cover owner-scoped create/get/action workflows, idempotency
  replay/conflict, stale-version rejection, accept/reject/edit/alternative,
  lock/unlock, undo/redo, restore, clarification answers, immutable versions,
  provider-run metadata, and redacted audit events.
- Provider tests cover the deterministic local provider, malformed remote output,
  disabled provider behavior, HTTPS/API-key configuration, response-size limits,
  bounded retry, and circuit-breaker failure handling.
- Migration tests assert every Phase 6 table is owner-scoped, internal foreign
  keys include `owner_user_id`, and migration `20260719_0007` matches registered
  SQLAlchemy metadata.
- API tests cover authenticated creation, edit rejection for ungrounded text,
  accept/undo/answer/get, no-store/ETag behavior, CSRF requirements, and
  cross-user denial.
- Web component tests cover loading, empty, success, failure, provenance-visible
  suggestions, canonical score disclaimer, accept and clarification-answer
  actions, and absence of demo/mock suggestions.
- The Phase 6 Playwright journey registers and verifies a real account, creates
  confirmed fictional evidence, saves/analyzes a pasted job, opens Change
  Studio, generates grounded suggestions, reviews provenance, accepts, undoes,
  and answers a clarification.

`scripts/verify-phase6.ps1` is the consolidated local gate for the final Phase 6
tree. It verifies migration head `20260719_0007`, rollback to `20260719_0006`,
forward repair, real integration tests, prior Playwright journeys, and the new
Change Studio primary workflow.

## Resume Builder and verified export coverage (Phase 7)

Phase 7 keeps every Phase 6 gate and adds blocking coverage for ADR 0013:

- Service tests cover owner-scoped create/list/get/update, evidence-required
  bullet validation, autosave/version creation, immutable restore/history,
  export idempotency replay/conflict, blocked-export download denial, deletion,
  and redacted audit/status behavior.
- Renderer/workflow tests generate real PDF and DOCX bytes from all five
  distinct templates and reparse them through the independent local document
  extractor. Exact Unicode occurrences, omissions, duplicates, order,
  searchability, one/two-page overflow, unsupported/numeric grounding, and
  version/manifest hash drift are blocking; failed objects are removed.
- Durable workflow tests cover transactional outbox delivery, typed
  render/delete operations, lease and acknowledgement fencing, duplicate
  delivery, bounded retry, publish/processing/cleanup dead letters, redacted
  audit, lost-message reconciliation, truthful object deletion, cancellation
  immediately after a successful object write, attempt-key isolation, and
  retry/dead-letter recovery of the precommitted orphan-object backstop.
- Migration tests assert every Phase 7 table is owner-scoped where required,
  composite foreign keys include `owner_user_id`, historical migration
  `20260719_0008` remains immutable, and closure heads `20260726_0012`/
  `20260726_0013` match registered SQLAlchemy metadata without drift. The latter
  restores inconsistent historical deletion state to queued cleanup without
  inventing timestamps.
- Repository integration uses real PostgreSQL to persist resumes, versions,
  exports, operation-typed outbox state, verification reports, idempotency
  records, download intents, render/cleanup audit transitions, private S3
  transfer/deletion, and cross-user denial.
- API tests cover authenticated resume creation/update/export/download-intent
  workflow, CSRF requirements, idempotency headers, `If-Match` handling,
  verification-blocked exports, no-store/ETag behavior, and safe problem
  responses.
- Existing web component and browser suites must remain compatible with the
  additive API contract. This non-frontend closure does not add editor behavior;
  it retains the authenticated Resume Builder export/download journey while API,
  worker, repository, and fidelity suites exercise the new durable states.

`scripts/verify-phase7.ps1` is the consolidated local gate for the final Phase 7
tree. It verifies current migration head `20260726_0013`, rollback to
`20260719_0007`, forward repair, real PostgreSQL/S3 integration, prior
Playwright journeys, and the Resume Builder desktop/mobile primary workflow.
The recorded 2026-07-19 gate remains the historical baseline; current closure
results must be recorded separately in `PLANS.md`.

## Application Workspace and grounded-pack coverage (Phase 8)

Phase 8 keeps every Phase 7 gate and adds blocking coverage for ADR 0014:

- Domain and service tests cover stage/outcome/reopen rules, owner scope, strict
  optimistic concurrency, stable idempotency replay and fingerprint conflict,
  resume-change reason/audit history, task/note/event creation, application and
  document deletion, pack generation, numeric grounding, and cross-document
  consistency. Database-backed tests require stage/outcome enum parity and prove
  that a resume change, refreshed evidence snapshot, workflow event, and audit
  record commit or roll back as one real transaction.
- Source-adapter tests require the exact job ID/version/source hash and
  requirement snapshot; immutable resume ID/version/number whose per-claim hashes
  are revalidated; and evidence ID/revision ID/revision number/statement hash.
  Historical revisions are read explicitly. A legacy Change Studio claim remains
  readable for history but cannot seed Resume Builder; a legacy resume/change
  source without the complete provenance ledger cannot seed Application
  Workspace. Neither path silently backfills current evidence into old history.
- Migration tests assert every Phase 8 child carries explicit owner and
  application scope, composite foreign keys prevent cross-owner nesting, stage
  and outcome values are constrained, and migration `20260724_0009` matches the
  registered SQLAlchemy metadata. Upgrade-compatibility cases keep the shipped
  `20260719_0007` migration immutable, prove that Phase 8 forward-adds an
  all-null/all-complete Change Studio evidence revision tuple, preserve an
  existing claim as readable but explicitly unpinned, and require full pins for
  every new claim.
- Repository and API tests cover two-user denial, nested-parent denial, bounded
  filters/calendar ranges and opaque cursors, independent pagination for tasks,
  notes, events, and pack summaries, no-store responses, ETags/`If-Match`, CSRF,
  stable idempotency, terminal-state conflict, tombstoned document content, and
  redacted audit metadata. Opaque cursors reject non-ASCII input before decoding,
  and an omitted event time remains stable across an idempotent retry instead of
  adding the current clock to its request fingerprint.
- Web component tests cover stale base/cursor response rejection, cursor reset
  after filter/error changes, paginated saved-job selection, one stable
  idempotency key per unchanged user intent, key rotation after an edit or
  success, lazy child-panel loading, preserved drafts across tab changes, live
  task/pack counts, semantic grouped controls, and accessible loading, empty,
  success, failure, retry, and conflict states. Conflict handling reloads
  authoritative state without allowing a stale response to overwrite it.
- The Phase 8 Playwright journey registers and verifies a real account, creates
  confirmed fictional evidence, saves and analyzes a job, creates an immutable
  resume and application, exercises board/table/calendar and non-drag stage
  control, records tasks/notes/events, and generates and reviews a grounded pack
  and its consistency result. The same complete product journey passes separately
  on desktop and mobile; outcome/deletion/audit behavior is covered by backend/API
  suites, and the mobile path includes the keyboard-safe alternative to
  pointer-only stage/view changes.

Final local closeout passed on 2026-07-24 for implementation revision `964cd9c`.
`scripts/verify-phase8.ps1` exited 0 in 273 seconds: the backend portfolio
reported `206 passed`, the API portfolio `104 passed`, and the web portfolio
`121 passed` across 35 files; the production build emitted 39 routes. The
isolated database reached head `20260724_0009`, rolled back to
`20260719_0008`, and repaired forward. Integration, worker, runtime, and
container probes passed. Playwright discovered 16 tests and completed with 10
passed and 6 intentional inherited mobile skips; Application Workspace itself
passed its full desktop and mobile journeys.

The separate `scripts/security-scan.ps1` exited 0 in 287.7 seconds. Gitleaks was
clean, pnpm and pip audits found no known vulnerabilities (unpublished local
workspace packages were skipped), API and worker had no fixable-high findings,
and web plus `web-edge` had no vulnerabilities. Three medium Python-runtime
findings remain with fixes only in Python 3.15 prereleases; they are nonblocking
under the documented policy and remain tracked. PR #21 workflow runs
`30126993025` and `30128304892` passed every required hosted job. The replacement
implementation run followed a test-only pagination correction that traverses
every cursor page; the fresh-database integration suite also passed in full.

## Interview, networking, growth, and analytics coverage (Phase 9)

Phase 9 retains every Phase 8 gate and adds blocking coverage for ADR 0015:

- Interview service/repository/API tests cover exact claim/evidence revision and
  statement-hash pins, undefended strong-claim warnings, story/session/note
  owner and nested-parent denial, immutable source snapshots, strict versions,
  idempotent question/follow-up generation, deletion/audit, non-ASCII cursor
  rejection, and the absence of any send action. New ready-story and generation
  adversarial cases reject revoked, revised, downgraded, unavailable, conflicted,
  unsafe-attachment, unsupported-number, and cross-owner evidence while
  preserving draft history and exact immutable idempotent replay. Defense Map
  cases revalidate matching ready stories and classify stale support as
  partial/needs-review without rewriting it. Real PostgreSQL cases verify that
  ready-story validation precedes story/idempotency/audit persistence and
  serialize duplicate question-bank generation and per-session child quotas;
  owner/session/idempotency locks prevent create races.
- Networking tests cover owner/contact/organization scope, explicit grant and
  withdrawal ordering for each consent purpose, denial before consent,
  collection/storage parent tombstoning and full child redaction, outreach-only
  preservation of notes and non-template, non-referral inbound/mutual history,
  outbound/template/referral/reminder redaction, prevention of any terminal
  transition from restoring redacted sensitive content, organization detachment,
  and safe explicit reminder reactivation that creates a fresh occurrence/outbox
  rather than reusing terminal work. Cursor cases reject values across
  owner/collection/parent/filter/sort purposes, stable keysets, idempotency
  fingerprints, version conflicts, race-safe collection quotas, recurrence,
  composite reminder-occurrence ownership, occurrence/outbox/audit trace
  propagation, safe terminal-history pruning, dead-letter preservation, leases,
  retry/dead-letter/recovery, and the allowlisted read-only reminder execution
  view. Wire, service, and fresh-PostgreSQL cases also reject arbitrary consent
  policy text and verify that every retained ledger field is content-free. They
  assert that no scrape/import/delivery interface exists.
- Career Growth golden and boundary cases cover goal/milestone and
  development transitions, exact evidence pins, completed-certification evidence
  requirements, completed annual-resume-refresh evidence, achievement-only
  history, skill-evidence coverage, six-check Promotion Readiness, current
  evidence revalidation and idempotent immutable review finalization/versioning,
  stale/revoked exact-pin exclusion from promotion/finalized-review/annual-refresh
  insight checks and returned annual links, deletion/audit, Career Health
  component weights/age bands/cadences/rounding/labels, snapshot tamper
  rejection, insufficient data, and the canonical disclaimer.
- Analytics aggregation tests cover complete keyset traversal beyond one page,
  source-watermark drift before/after work, eligibility-only point-set drift,
  exact window-aware supplemental watermarking, durable idempotent refresh/outbox
  processing, duplicate delivery, retry/dead-letter/reconciliation, bounded
  Role Readiness source overflow with stable `source_limit_exceeded` retry state,
  transient supplemental failure with stable `source_unavailable` state, public
  3,648/3,649/3,650-day boundary windows and date-min/date-max guard clamping,
  shared API/worker resume and clean-attachment eligibility composition, durable
  trace rebinding,
  stale fail-closed reports, five-record suppression, scope/window bounds, owner
  isolation, exact selected-cohort event buckets, IANA timezone midnight
  boundaries, timezone-specific snapshot identity, versioned
  metric/cohort/timestamp/suppression definitions, requirement-coverage trends,
  exact resume-version outcomes, owner active/history quotas, payload tamper
  rejection, purpose-minimized source fields, canonical-eligible
  achievement-only growth, and rejection of causal, prediction, or guarantee
  language.
- Migration tests cover a fresh `20260724_0010` schema, all four repository
  contexts, owner/composite foreign keys, check/index parity, rollback to
  `20260724_0009`, forward repair, and a pre-release Phase 8 database stamped
  without its canonical provenance tuple/check and resume-change event/audit enum
  values. Negative PostgreSQL cases reject orphan/wrong-owner Growth targets,
  mismatched or tampered evidence ID/revision/number/timestamp/hash provenance,
  including mutations of non-key link fields, cross-review or skipped
  predecessors, mismatched latest review tuples, invalid occurrence/outbox trace
  IDs, and reminder occurrences whose owner/contact/reminder tuple disagrees.
  A two-transaction PostgreSQL regression proves Growth target deletion waits
  for an in-flight evidence-link insert and cleanup cannot leave an orphan.
  The repair leaves Phase 8-owned objects intact on downgrade and produces a
  clean metadata check.
- Worker tests cover UUID-only analytics payloads, transactional outbox publish
  transitions, lost/expired leases, bounded retry and dead-letter handling,
  per-invocation database disposal, safe structured logs, local-only reminder
  occurrence processing, persisted reminder trace binding in log context, and the
  absence of content/destination/provider payloads. Analytics regressions assert
  that dead-letter and expired-lease recovery atomically terminalize the paired
  job rather than leaving an orphaned `queued` record.
- Web component tests cover loading/empty/success/failure/conflict states,
  request epochs and aborts, stable per-intent idempotency, quoted versions,
  cursor-based load-more, exact disclaimers and non-causal text, suppressed
  values, Growth achievement/skill/promotion/annual-refresh insights, Analytics
  coverage/version tables and timezone definitions, execution failures,
  keyboard/mobile/reduced-motion behavior, and non-color text/table summaries.
  The Phase 9 Playwright portfolio exercises all four workspaces on the
  production web/edge and API/worker stack, including the new Growth and
  Analytics outputs on desktop and mobile.

`scripts/verify-phase9.ps1` is the consolidated Phase 9 gate. It requires
migration rollback/repair, repository/API/worker integration, generated
contracts, production build, predecessor browser journeys, and the new complete
desktop/mobile Phase 9 journey. The latest complete stack execution before the
exact-claim interlock passed with 347 backend, 123 API, 84 worker, and 146 web
tests across 43 files; the production build emitted 48 routes. PostgreSQL
integration passed 37 tests with 7 inherited SQLAlchemy cycle warnings.
Playwright passed 12 tests with 6 intentional inherited mobile skips, and the
Phase 9 desktop/mobile journeys both passed. A transient Docker Desktop 502
occurred only while the wrapper restored the primary stack after all checks;
bounded restoration retries are now present. After the exact-claim interlock,
the complete backend and API portfolios pass 355 and 134 tests respectively, so
one exact final-tree consolidated stack rerun remains mandatory.

Closeout regressions also prove one stale story does not contaminate another;
delayed STAR-story creation and career-review finalization retries return their
immutable historical results; Networking does not materialize interview content
for an application ID/stage lookup and serializes organization deletion against
contact reassignment; Analytics aliases cannot weaken generated required fields,
joint outbox/job claims use a job-version causal acknowledgement fence, lease
validity is checked after the final watermark, terminal failures log safe codes,
and account deletion preserves audit ownership invariants. Exact resume
provenance rejects reviewed text that differs from the immutable extracted block,
requires an exact whole-block statement digest, rejects metadata/link scope
injection, dynamically excludes mismatched legacy rows, and removes accepted
legacy import context after a factual entity edit. Case, internal whitespace,
punctuation, number, homoglyph, subset, and superset adversarial cases are
covered; boundary whitespace alone is accepted.

The prior security execution found Gitleaks, `pnpm audit`, and `pip-audit` clean
for actionable source/application dependencies, while web and `web-edge` images
had no vulnerability. The `brace-expansion` advisory remains resolved by the
`5.0.8` workspace override and minimatch 3.1.5/5.1.9 compatibility patches. The
only nonblocking runtime findings were the three medium CPython 3.13.14 CVEs
listed in `PLANS.md`, whose fixes are available only in Python 3.15 prereleases.
The exact merged tree passed the separate security gate again. PR #22 workflow
run `30161489265` passed every required hosted job at implementation/merge head
`1454792`.

Phase 7 closure covers durable asynchronous Resume Builder render/verify/cleanup
dispatch and recovery plus distinct-template cross-format fidelity. Phase 10A
adds pure coverage for deterministic Phase 1-9 graph construction, exact
provenance/export hashes, the `20260726_0013` migration pin, fail-closed
environment/database/object guards, and existing-object drift refusal. The live
acceptance gate ran the guarded command twice against the same PostgreSQL/MinIO
state: pass one verified 79 newly created rows and two private objects; pass two
verified the same 79 rows and objects while creating zero rows and preserving
the account. The presentation-only `pnpm fixtures:preview` remains deliberately
separate and performs no database or object-store I/O.

## Backend test portfolio

- **Domain/unit:** evidence state transitions, claim eligibility, job/application
  stage machines, idempotency, score features/formulas/rounding/missing data,
  permission decisions, retention/deletion plans, consistency rules.
- **API:** schemas, safe problems, pagination/filter/sort bounds, body/rate limits,
  correlation IDs, CSRF/auth, ownership, stale versions, idempotency concurrency,
  audit assertions, content negotiation.
- **Database:** constraints/indexes/FKs, ownership-scoped queries, vector/search
  scope, optimistic concurrency, transactions/outbox, migration upgrade from prior
  release, empty bootstrap, representative data migration, forward repair.
- **Queue:** enqueue transaction boundary, duplicate/reordered task, timeout,
  retry classification/cap, cancellation, progress, dead letter, trace/ownership,
  cost, worker crash and safe resume.
- **Providers:** deterministic fake contract plus opt-in adapter contract; timeout,
  malformed response, rate limit, partial failure, redaction, circuit breaker.
- **Files/exports:** hostile admission, parser corpus, cleanup, object isolation,
  rendering and reparse comparison.

Authorization tests use at least two users in different tenants, two users with
different roles in one organization when introduced, an anonymous principal, and
an administrator without raw-document capability. They attempt direct ID, nested
resource, search, list, export, signed URL, background job, cache, and analytics
access.

## Frontend test portfolio

- **Unit:** formatting and mapping functions, score/disclaimer helpers, state
  reducers, validation, accessible labels/text summaries.
- **Component:** loading/empty/success/error, long/localized content, focus and
  keyboard behavior, dialog return focus, non-drag reorder, tables/charts/diffs,
  color-independent states, reduced motion.
- **Contract integration:** query/form behavior against schema-typed clients and a
  schema-faithful mock server; error, conflict, rate limit, retry, cancellation.
- **E2E:** registration/session, onboarding, upload/correction/report, profile/
  evidence, role/job matrix, Change Studio review, export verification/restore,
  application/interview/contact, export/deletion.
- **Responsive:** large desktop, laptop, tablet, and representative narrow mobile;
  approval/review remains functional even when editing is desktop-optimized.
- **Accessibility:** automated checks plus manual keyboard/rendered review of each
  primary workflow; representative screen-reader review is required before
  production release. Automation alone does not prove WCAG 2.2 AA.

Visual regression may protect core shell/templates after the design stabilizes.
It must mask dynamic timestamps/IDs and cannot replace semantic/accessibility tests.

## Document fixture matrix

All benign resume content is fictional. Binary fixtures are licensed/created for
test use and documented with expected canonical data and checksums.

| Fixture                        | Primary assertions                                                            |
| ------------------------------ | ----------------------------------------------------------------------------- |
| Clean one-column PDF           | Complete text, sections, fields, reading order                                |
| Two-column PDF                 | Reading order warning/correct extraction, no silent interleave                |
| DOCX                           | Paragraph/list/table handling and canonical spans                             |
| Header/footer                  | No lost/duplicated essential fields; warning if essential content lives there |
| Table-based resume             | Safe extraction and predictable warning                                       |
| Image-only PDF                 | Detection and OCR-disabled/enabled behavior                                   |
| Multiple date formats          | Normalization without invented day/month; locale uncertainty                  |
| Concurrent roles/promotions    | No false conflict; correct grouping and dates                                 |
| Career gap                     | Neutral representation, no automatic negative scoring                         |
| Long resume                    | Page/size limits, bounded time/memory, clear error/warning                    |
| Malformed/truncated file       | Safe failure, no stack/raw content leak, cleanup                              |
| Wrong extension/polyglot       | Byte signature wins; reject/quarantine                                        |
| Oversized/decompression bomb   | Admission/expansion limit before exhaustion                                   |
| Macro/embedded attachment/link | Never execute; reject or safely ignore under policy                           |
| Prompt injection in resume     | Treated as content; cannot change AI policy                                   |
| Prompt injection in job text   | Treated as content; cannot change extraction/grounding policy                 |

Add encrypted, unusual font/encoding, bidirectional Unicode, duplicate page,
symlink/path traversal archive, and EICAR scanner fixtures where the selected
libraries/formats make them relevant. Malware fixtures run only in isolated
approved test environments and are never executable.

Phase 2 commits deterministic fictional one/two-column PDF, DOCX, image-only,
header/footer, table-heavy, date-locale/concurrent-role, career-gap,
long-resume, unusual-font, and bidirectional-control coverage with a checksum
manifest. Hostile PDF/DOCX/ZIP cases are assembled in isolated unit tests, and
the scanner integration assembles the standard antivirus test signature at
runtime rather than committing it. These fixtures assert structural signals and
safe bounded behavior; they do not claim full visual rendering fidelity.

PDF fixtures exercise the authoritative page cap. The local `python-docx`
extractor does not expose reliable rendered page count, so DOCX tests instead
prove upload-byte, archive-entry, expanded-size/ratio, extracted-character/block,
artifact-size, and runtime bounds. Layout-aware DOCX page-limit coverage waits
for a rendering provider and must not be inferred from the PDF test.

## Scoring tests

- Unit test each feature, cap, denominator, state credit, importance, gate,
  threshold, fixed-decimal aggregate, and half-up display rounding.
- Golden fixtures calculate expected features/components/total independently.
- Repository/API round trips preserve historical `resume-health-features/1` and
  current `resume-health-features/2`, every version-eligible typed feature value,
  and exact component feature score/weight/contribution basis points;
  generated-contract parsers reject malformed or missing trace fields.
- Property tests assert determinism, `[0,100]` bounds, weight total, no divide-by-
  zero/NaN, expected monotonic behavior, and idempotent reanalysis.
- Assert unknown/missing/not-applicable differ; insufficient data returns no
  deceptively precise score; mandatory gaps remain visible under a high average.
- Assert an LLM/model candidate cannot directly set a feature or total without
  validated source span and deterministic conversion.
- Regression/fairness cases cover keyword duplication, career gaps, nontraditional
  chronology, locale/date/language, sparse data, and protected-characteristic
  proxies. Scores must not reward fabrication or penalize identity.
- UI tests assert exact canonical disclaimer, internal measure labels, accessible
  text/table summary, and no hiring probability/guarantee language.

Formula/config versions are immutable test inputs. A changed expected number must
name the new version and rationale; blindly updating snapshots is prohibited.

## AI and grounding tests

- Strict schema validation: malformed JSON, unknown fields, oversized/bad enums/
  ranges, bogus IDs, multiple claims hidden in one field.
- Unsupported invention for every protected fact class and cross-tenant/deleted/
  archived/inferred/unsupported evidence.
- Numeric value/unit/sign/period/baseline/denominator/approximation/attribution;
  each generated metric maps to confirmed/verified evidence.
- Entity/date/technology/credential consistency, team-to-sole-ownership,
  participation-to-leadership, association-to-causation, changed certainty.
- Prompt injection through resume/job/evidence/HTML/Unicode/encoded text; attempts
  to reveal policy/secret or invoke shell/SQL/URL/path/tool.
- Clarifying questions stay neutral and support skip/not-applicable; normalized
  answers require explicit confirmation.
- Provider timeout/rate/malformed/partial output, bounded retry, idempotent cost,
  quota/circuit breaker/kill switch, and redacted telemetry.
- User accept/reject/edit/regenerate/undo/redo/lock/restore; final edits revalidate
  and prior/exported versions remain immutable.
- Application consistency detects conflicting dates/titles/metrics/claims.

The deterministic fake returns golden candidates, including deliberately unsafe
ones; tests exercise the real schema/grounding pipeline, not a fake “already
grounded” boolean.

## Critical acceptance matrix

| Requirement                                 | Minimum blocking test                                                                                     |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| No cross-user resume access                 | API, list/search, object/download, worker-status, and cache tests mutate user/tenant/resource IDs         |
| Unsupported claim cannot be accepted        | Adversarial candidate and manual edit both fail grounding and version creation                            |
| Generated metric maps to confirmed evidence | Ledger-to-metric source assertion plus unit/period/attribution mismatch cases                             |
| Job instruction cannot override policy      | Injection corpus returns extracted content only, never policy/tool behavior                               |
| Malformed upload fails safely               | Parser isolation test asserts bounded resources, quarantined status, cleanup, safe error/log              |
| Export parses back                          | Each template/format compares critical canonical fields/claims and blocks critical mismatch               |
| Restore prior version                       | New current version references ancestor; old/exported bytes/hash stay unchanged                           |
| Delete uploaded document                    | User-owned relational/object/derived/vector/cache/job artifacts removed/scheduled; other user untouched   |
| Account deletion                            | Sessions revoke and per-store deletion state reaches policy-complete including provider/backup disclosure |
| Keyboard-accessible workflows               | Manual plus automated tab/order/focus/activation/non-drag tests across every primary journey              |

## Security and privacy test methods

- Run secret, SCA, container, and IaC scans in CI; pin third-party actions/images
  and retain actionable reports. A scanner outage is visible, not a green pass.
- Use a local adversarial HTTP server to test SSRF redirects, DNS/address forms,
  response size/time/content types; production also needs egress-firewall tests.
- Send PII/secret canaries through safe test requests and assert they do not appear
  in logs, traces, analytics, errors, queue metadata, or provider snapshots.
- Exercise rate and cost limits concurrently and through alternate harmless
  headers/address representations; do not run abuse tests against production.
- Verify admin capability matrix, recent authentication, redaction, sensitive
  access audit, safe retry, and destructive dual-control policy when implemented.
- Restore backups to an isolated environment and verify integrity/ownership/object
  links/migrations; destroy restored sensitive test environment afterward.

## CI tiers

### Pull request gate

- frozen dependency install;
- format check, lint, strict types;
- unit/component/contract tests;
- backend and frontend architecture dependency checks;
- API import, normalized OpenAPI/generated-schema drift validation, and web
  production build;
- migration graph plus fresh/container upgrade validation when migrations exist;
- secret/dependency scanning and fast container build/smoke as infrastructure allows.

### Main/nightly gate

- real PostgreSQL/Redis/MinIO integration and worker tasks;
- Playwright critical journeys, responsive and automated accessibility;
- parser/export fixture matrix and adversarial grounding/SSRF subsets;
- container/security scans and flaky-test detection.

### Release gate

- full clean install/build/migrations;
- all integration/e2e/accessibility/adversarial/export suites;
- load/soak/failure, deletion, backup/restore, security review and production
  configuration validation;
- protected environment and manual approval. No automatic unprotected production
  deployment.

CI jobs publish JUnit/coverage/security reports and redacted diagnostics. Test
artifacts have short retention and no real private data.

## Flake, retry, and coverage policy

Product tests do not use automatic retries as proof of correctness. A CI-level
retry may diagnose infrastructure flakes but the first failure remains visible
and an unstable required test blocks phase completion until fixed. Quarantine
requires an owner, issue, expiry, and non-green phase/release decision for any
required behavior.

Coverage percentages are signals, not completion gates by themselves. Require
branch coverage of truth/authorization/score/state/error rules and explicit tests
for every security invariant. Do not add meaningless tests to raise a number.

## Failure triage record

For a failure, capture revision, exact command, environment/tool versions, seed/
fixture, failing assertion, sanitized request/trace ID, first-failure artifact,
and whether it is deterministic. Fix root causes; never replace an assertion with
a broad snapshot or sleep solely to make CI green.

Phase test commands and results are recorded in `PLANS.md` before completion.
