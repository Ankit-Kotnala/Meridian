# CareerOS testing strategy

Status: Phase 2 local suites pass; hosted CI evidence pending
Last reviewed: 2026-07-15

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
  updates, Google OAuth validation/collision behavior, and the streamed body cap.
- Two integration tests use isolated real PostgreSQL and Redis. They are selected
  explicitly by the full-stack runner and fail when dependency URLs are absent;
  the fast unit runner does not disguise them as skipped coverage.
- The migration gate exercises `20260714_0001` to `20260715_0002`, downgrade, and
  forward re-upgrade, and verifies the runtime image reports one expected head.
- Web/UI tests cover contract-bound requests, proxy allowlists and failures,
  validation, loading/empty/success/error feedback, session-bound CSRF, refresh
  coalescing, protected navigation, and accessible form primitives.
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
  features, persisted feature values/contributions, insufficient-data behavior,
  bounds, determinism, and two independently asserted golden score cases.
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
- Extractor tests use committed fictional clean PDF, DOCX, and image-only PDF
  fixtures plus test-generated wrong-signature, malformed, encrypted, polyglot,
  macro, traversal, expansion-entry, compression-ratio, and timeout inputs. The
  fixtures and manifest are deterministic and contain no user data.
- Integration tests use a migrated real PostgreSQL database for owner-scoped
  repository/job state, private S3-compatible storage for signed upload/promote/
  download/delete lifecycle, and real ClamAV with an isolated dynamically
  assembled standard test signature. They fail rather than skip when the Phase 2
  runner has not supplied its dependencies.
- API tests cover real policy values, account authentication/owner scope, opaque
  guest cookie scope and CSRF, neutral HMAC-signed per-source pre-auth/guest-upload
  rate keys, invalid/absent production signals, correction/analysis rate classes,
  exact idempotency/`If-Match` bounds, and score response feature-schema/value/
  contribution/hash/disclaimer behavior. Worker tests cover strict queue
  envelopes, allowlisted task publication, runtime failure mapping, fencing/busy
  retry, bounded maintenance inputs, and secure configuration.
- Web/UI tests cover filename/media/size validation, exact-origin direct upload,
  byte progress and abort, same-page in-memory intent/finalize retry, loading/
  empty/success/error states, processing and deletion semantics, immutable
  correction review, insufficient data, stored measured values and weighted
  contribution text equivalents, canonical disclaimer, keyboard interaction, and
  accessible file/progress/tab/dialog/disclosure primitives.
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
0 failures. Exact package counts are recorded in `PLANS.md`; hosted CI evidence
remains pending. This section is not completion evidence.

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

Phase 2 commits generated fictional one-column PDF, DOCX, and image-only PDF
fixtures with a checksum manifest. Hostile PDF/DOCX/ZIP cases are assembled in
isolated unit tests, and the scanner integration assembles the standard antivirus
test signature at runtime rather than committing it. Two-column, header/footer,
table-heavy, date-locale, concurrent-role, career-gap, long-resume, unusual-font,
and bidirectional-Unicode corpus files remain future fixture-matrix coverage;
they are not implied by the Phase 2 closeout suite.

PDF fixtures exercise the authoritative page cap. The local `python-docx`
extractor does not expose reliable rendered page count, so DOCX tests instead
prove upload-byte, archive-entry, expanded-size/ratio, extracted-character/block,
artifact-size, and runtime bounds. Layout-aware DOCX page-limit coverage waits
for a rendering provider and must not be inferred from the PDF test.

## Scoring tests

- Unit test each feature, cap, denominator, state credit, importance, gate,
  threshold, fixed-decimal aggregate, and half-up display rounding.
- Golden fixtures calculate expected features/components/total independently.
- Repository/API round trips preserve `resume-health-features/1`, every typed
  feature value, and exact component feature score/weight/contribution basis
  points; generated-contract parsers reject malformed or missing trace fields.
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
