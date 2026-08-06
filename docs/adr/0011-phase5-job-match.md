# ADR 0011: Phase 5 Job Match, Requirement Matrix, and Opportunity Priority

Status: Accepted
Date: 2026-07-19

## Context

Phase 5 needs exact job matching without weakening Rezumi truth invariants. Job
postings and imported descriptions are hostile input. Career claims must continue
to come from the owner-scoped Career Record readiness snapshot, and optional role
context must come through the Role Readiness application boundary. Scores cannot
be presented as employer, ATS, or hiring-probability scores.

## Decision

Add `rezumi.modules.job_match` as a bounded context with deterministic domain
scoring, owner-scoped application use cases, SQLAlchemy persistence, and thin
FastAPI/Next.js adapters.

- Store job postings, current extracted requirements, immutable match analyses,
  historical requirement match rows, evidence-link snapshots, opportunity
  priority analyses, idempotency fingerprints, versions, and redacted audit
  events in migration `20260719_0006`.
- Use the Career Record readiness snapshot provider for eligible evidence and a
  Role Readiness role-context provider for optional target role labels. Do not
  query another module's tables from Job Match.
- Extract requirements deterministically from the exact saved job text and store
  source spans for current job requirements. Historical analyses store their own
  requirement text/match rows so editing a saved job does not mutate old results.
- Implement URL import as HTTP(S)-only, bounded, redirect-limited, public-network
  validated, script/style-stripped plain text. Tests use deterministic fakes and
  direct SSRF policy unit coverage.
- Require authentication for all Job Match routes, CSRF for mutations,
  idempotency keys for create/import/analyze/priority, and `If-Match` versions
  for update/delete.
- Display the canonical internal-score disclaimer wherever Application Readiness
  or Opportunity Priority appears.

## Consequences

Phase 5 is explainable and testable without third-party credentials or AI
providers. Requirement matching is conservative because it uses deterministic
token overlap and eligible evidence snapshots rather than semantic retrieval.
Future scoring changes require a new engine/configuration version and regression
fixtures.

The stdlib URL importer validates each URL and redirect resolution before
opening the request, but it does not pin the socket to a specific resolved IP.
If URL import becomes production-critical, replace the transport with a
connect-to-validated-address adapter or a sandboxed fetch service that prevents
DNS rebinding at connection time.
