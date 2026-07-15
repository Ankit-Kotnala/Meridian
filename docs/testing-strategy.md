# CareerOS testing strategy

Status: aligned local Phase 0 gate passed; hosted CI rerun pending
Last reviewed: 2026-07-14

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
- E2E starts from an explicit seed and cleans up. Retries must not hide failure;
  CI retains trace/screenshot/video only with fictional/redacted content.
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

The expanded repository gate passes in the current aligned working tree. The
earlier foundation baseline remains historical evidence only. Phase 0 stays open
until the aligned tree is committed and hosted CI passes for that exact revision.

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
- **Accessibility:** automated checks plus manual keyboard/screen-reader review of
  each primary workflow. Automation alone does not prove WCAG 2.2 AA.

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

## Scoring tests

- Unit test each feature, cap, denominator, state credit, importance, gate,
  threshold, fixed-decimal aggregate, and half-up display rounding.
- Golden fixtures calculate expected features/components/total independently.
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
