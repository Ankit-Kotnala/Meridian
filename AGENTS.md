# CareerOS repository rules

This file applies to the entire repository. A more specific `AGENTS.md` may add
rules for a subtree, but it must not weaken the safety, truthfulness, privacy, or
verification requirements below.

## Product invariants

1. The structured career profile and its evidence graph are the source of truth.
   A resume, application answer, cover letter, profile summary, networking
   message, and interview story are derived outputs.
2. Never invent an employer, title, date, responsibility, accomplishment,
   number, technology, credential, education record, award, leadership claim,
   or ownership claim. Missing facts produce a question, not prose that looks
   factual.
3. Every generated factual claim must carry machine-checkable provenance to
   eligible evidence. Numbers require user-confirmed or independently verified
   evidence. Unsupported evidence is never generation input.
4. Never apply a material career-document change silently. Preserve the original,
   reason, evidence, relevant requirement, and an explicit accept/reject/edit
   path. Published or exported resume versions are immutable.
5. Never describe an internal score as an employer or applicant-tracking-system
   score, a hiring probability, or a guarantee. Show the canonical disclaimer
   defined in `docs/scoring-methodology.md` wherever a score could be
   misunderstood.
6. Analytics describe correlations and observed patterns, not causation.

## Architecture boundaries

- `apps/web`: Next.js App Router user experience. It does not access databases,
  object storage, or queues directly.
- `apps/api`: thin FastAPI HTTP delivery application and OpenAPI source of truth.
  It owns transport validation and composition, not domain rules or persistence
  implementations.
- `apps/worker`: thin Celery delivery application for isolated asynchronous work.
  Tasks call backend application use cases and never duplicate business rules or
  import `apps/api`.
- `packages/backend`: shared Python modular-monolith implementation. Stable,
  domain-independent database, configuration, migration, and observability
  primitives live in `careeros.foundation`; product code is added under
  phase-owned `careeros.modules` and provider SDK adapters under
  `careeros.integrations` only when those phases begin.
- `packages/ui`: accessible, presentation-oriented React primitives. It must not
  depend on application routes or private API implementation details.
- `packages/contracts`: normalized OpenAPI artifacts, generated TypeScript types,
  and a typed `openapi-fetch` client wrapper. FastAPI schemas are authoritative;
  do not create parallel handwritten wire models or hand-edit generated artifacts.
- `packages/design-tokens`: reusable visual tokens without product behavior.
- `packages/eslint-config` and `packages/typescript-config`: shared strict build
  and dependency-boundary configuration without runtime credentials.
- `packages/test-fixtures`: explicitly fictional, non-sensitive fixtures only.
- `infra`: local and deployment infrastructure. Production changes require an
  ADR, rollback plan, and protected-environment review.

The root uv workspace and its single lockfile cover `apps/api`, `apps/worker`,
and `packages/backend`. Both deployable Python applications depend on the backend;
the backend imports neither deployable, and the worker never imports the API.
Within a backend product module, dependency direction is API/task adapter to
application use case to domain model and port, with infrastructure implementing
the inward-facing ports. Domain code must not import FastAPI, SQLAlchemy, Redis,
object storage, queue libraries, or provider SDKs. One module must use another
through an explicit application service, query interface, or event rather than
querying its tables directly. Architecture tests make these rules executable.

Keep dependency direction toward generated contracts and domain services.
Provider-specific code belongs behind interfaces such as `ResumeParserProvider`,
`DocumentTextExtractor`, `LayoutAnalyzer`, `MalwareScanner`, `OcrProvider`,
`JobImportProvider`, AI provider, billing provider, and error-monitoring provider.
Local development and tests must remain usable without third-party credentials
through deterministic local or fake adapters.

Next.js route files remain thin. Product behavior and domain-specific UI belong
under `apps/web/src/modules/<feature>`; reusable framework-neutral UI belongs in
`packages/ui`. Enforce frontend boundaries with lint/dependency checks. Do not
create generic dumping grounds named `common`, `helpers`, `misc`, `services`, or
`utils`.

## Data, tenancy, and authorization

- Use UUIDs for externally visible and domain entity identifiers.
- Every user-owned row and object must have explicit user or tenant ownership.
  Fetch by both ownership scope and resource ID; never authorize merely because
  the client knows an ID.
- Organizations are a future-compatible tenancy layer. Individual accounts must
  work without a synthetic organization, but schemas and policies must not block
  later organization membership.
- Put authorization checks in the API/service boundary and test cross-user denial.
  A hidden UI control is not authorization.
- Add foreign keys, constraints, indexes, and optimistic concurrency where the
  model needs them. Use soft deletion only for a stated retention, restore, or
  audit reason.
- Do not log raw resumes, job descriptions, evidence text, access tokens,
  passwords, signed URLs, or unnecessary PII. Structured logs use request and
  trace IDs and redacted identifiers.

## Security requirements

- Treat uploads, imported job descriptions, URLs, parsed text, and model output
  as hostile input.
- Validate MIME type and file signature, size and page limits, archive expansion,
  and randomized object keys before document processing. Uploaded content is
  never executed. File parsing runs in a resource-limited worker without
  unnecessary network access and always cleans temporary files.
- URL imports allow only HTTP(S), validate every resolved address and redirect,
  block private/link-local/loopback destinations, cap time and response size,
  sanitize content, and never execute remote scripts.
- Validate AI output against strict schemas and grounding policy before display.
  Never route model output directly to a shell, SQL statement, HTML sink, or file
  path.
- No secret or production credential may be committed. `.env.example` contains
  names and safe local defaults only.
- Authentication is a Phase 1 feature. Its design uses Argon2id and server-side
  sessions/rotating hashed refresh tokens in secure HTTP-only cookies, CSRF
  defenses, abuse controls, invalidation, and audited account deletion.
- Follow the controls and open risks in `docs/security-threat-model.md`.

## API and background jobs

- Product APIs live below `/api/v1`. Health probes may remain unversioned.
- Validate request and response payloads. Use the standard problem schema,
  correlation IDs, pagination, bounded filters/sorts, rate and body-size limits,
  and ownership-aware authorization.
- Require idempotency keys for retried side-effecting operations such as analysis,
  generation, export, webhook handling, and safe job retries.
- Every background job defines ownership, idempotency, timeout, bounded retry,
  dead-letter behavior, status, trace ID, and AI cost metadata when applicable.
- The OpenAPI document is the wire-contract source. Regenerate the normalized
  OpenAPI artifact and TypeScript client in the same change as an API schema
  change, and fail CI on unexplained drift.

## Frontend and accessibility

- TypeScript remains strict. Use semantic HTML and accessible primitives.
- Target WCAG 2.2 AA: full keyboard operation, visible focus, adequate contrast,
  labels and error associations, reduced-motion behavior, text chart summaries,
  and non-drag alternatives.
- Every data-driven view implements loading, empty, success, and failure states.
  Important approval workflows remain usable on mobile.
- Color reinforces meaning but never carries it alone. Red is reserved for
  critical gaps, not decoration.
- Hardcoded product metrics are prohibited. Fictional demo fixtures must be
  prominently labeled and isolated from production data paths.

## Engineering workflow

1. Read `README.md`, `PLANS.md`, applicable ADRs, and the closest `AGENTS.md`.
2. Inspect the worktree before editing. Preserve unrelated or user-authored work.
3. Keep work inside the active phase. Record a new cross-cutting decision in an
   ADR before introducing a competing framework or architectural path.
4. Include validation, failure handling, authorization, audit behavior,
   documentation, and proportionate tests in the same change as a feature.
5. Run the narrowest checks while iterating, then the repository gates before
   claiming completion:

   ```sh
   make format-check
   make lint
   make typecheck
   make test
   ```

   Run `make test-integration` and `make test-e2e` when the changed surface has
   those suites. Run `make verify` for the full Phase 0 gate.

6. Never report a phase complete if a required command failed, was skipped, or
   could not run. State the exact command, result, and blocker in `PLANS.md`.
7. Update relevant docs and `PLANS.md` status in the same change. Record remaining
   risks and the next safe step.

Create directories only when their owning phase has real implementation or test
content. Do not add empty extension, module, integration, operations, Terraform,
or repository-test scaffolding and do not present reserved paths as implemented
functionality.

Pinned dependencies are changed intentionally through their owning package tool
(`pnpm` or `uv`), with lockfiles committed. Prefer conservative compatible stable
versions; do not introduce preview dependencies without an approved ADR.
