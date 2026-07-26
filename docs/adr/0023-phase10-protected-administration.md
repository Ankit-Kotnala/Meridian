# ADR 0023: Persisted least-privilege platform administration

Status: Accepted
Date: 2026-07-27

## Context

CareerOS needs operational visibility and narrowly controlled recovery without
turning an application account into an unrestricted database or raw-document
reader. Existing feature-owned workers expose content-free durable states, but
there was no platform authority boundary, no uniform redacted dead-letter view,
and no audited manual recovery path.

Administrative policy, named operators, support processes, and a production
identity provider remain owner decisions. The application must therefore start
with no operator and must not infer authority from an email domain, organization
role, deployment environment, or hidden frontend control.

## Decision

1. `careeros.modules.administration` is the protected administration bounded
   context. It owns persisted operator assignments, feature-flag metadata,
   idempotency records, and a dedicated administration audit chain.
2. Operator assignments start empty. There is no HTTP endpoint that grants,
   changes, or revokes platform authority. Initial and lifecycle provisioning is
   an offline protected-environment operation until the owner approves an
   operator-governance policy.
3. Four roles map to explicit capabilities:
   `operations_viewer`, `job_operator`, `catalog_auditor`, and
   `security_auditor`. Authorization is resolved from the database on every
   request; application sessions carry no cached admin claim.
4. Every protected read and mutation requires a bounded purpose reason and
   writes a content-free audit event. Mutations additionally require CSRF,
   recent authentication, and idempotency where retryable.
5. Audit events are serialized under a PostgreSQL advisory transaction lock and
   linked with SHA-256. The chain includes a context-separated HMAC actor
   reference. The nullable user foreign key may be redacted during account
   erasure without changing the material covered by the chain.
6. Operational reads return only aggregate counts, UUIDs, state, attempt
   counters, timestamps, and allowlisted safe error codes. Raw resumes, evidence,
   notes, job descriptions, emails, provider payloads, object keys, and tokens
   are never available through this boundary.
7. Manual retry is an explicit allowlist. Phase 10F supports account-privacy and
   organization-invitation dead letters because both have deterministic,
   database-backed re-arm semantics. Each target has one audited manual retry
   budget, and replay of the same request key returns the prior result.
8. Other dead-letter kinds are visible but marked non-retryable. Their
   feature-owned reconciliation remains authoritative until a separately tested
   recovery adapter exists.

## Consequences

- A database compromise can alter the audit table, but alteration is detectable
  by chain verification. Production database audit export/WORM retention is a
  Phase 10H deployment control.
- Rotating the administration audit pepper requires retaining the previous
  secret while old actor references remain operationally useful; the hash chain
  itself does not depend on re-deriving those references.
- Account deletion removes assignments and idempotency state, nulls the audit
  actor FK, and retains only the pseudonymous HMAC reference and purpose-bound
  operational history.
- Adding a new manual retry kind requires a state-machine review, a single-use
  budget, redacted failure mapping, and live database coverage.
