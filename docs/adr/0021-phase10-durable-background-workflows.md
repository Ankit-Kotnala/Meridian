# ADR 0021: Phase-owned durable background workflows

- Status: Accepted
- Date: 2026-07-27
- Decision owners: Backend, platform, security, and release engineering
- Related: ADR 0013, ADR 0014, ADR 0015, ADR 0020

## Context

CareerOS already has durable, phase-owned job state for resume analysis, evidence
attachments, verified exports and cleanup, analytics refreshes, and networking
reminders. Organization invitation creation in Phase 10C atomically persisted an
outbox entry, but intentionally did not deliver email. A process crash, broker
redelivery, SMTP timeout, or concurrent scheduler must not lose an invitation,
mint multiple usable credentials, bypass expiry, or expose recipient/token data
in logs.

A new generic workflow framework would compete with the existing module-owned
state machines and obscure their domain-specific timeout, retry, cleanup, and
dead-letter policies.

## Decision

1. Durable workflow state remains owned by the product module that owns the
   business operation. Celery is delivery infrastructure, never the source of
   job truth.
2. Organization invitation delivery claims due rows with `FOR UPDATE SKIP
LOCKED`, a UUID lease token, and a bounded lease. Completion, cancellation,
   retry, and dead-letter transitions require that exact unexpired lease.
3. Invitation delivery is at-least-once. The credential is deterministically
   derived with a context-separated HMAC from the invitation identifier and the
   rotated server secret. Only its digest is persisted. A crash after SMTP
   acceptance may resend the same credential, but cannot create a second
   credential or weaken acceptance checks.
4. SMTP delivery has a bounded timeout, batch size, worker time limit, retry
   budget, exponential backoff capped at one hour, and terminal dead-letter
   state. Expired, revoked, accepted, or missing invitations cancel their
   outbox entries instead of sending.
5. The deployable worker composition root renders email and adapts the
   organization message to the shared SMTP integration. The organization module
   does not import Celery, SMTP, API routes, or identity email models.
6. Task payloads and telemetry contain operational counts and safe error codes
   only. Recipient addresses, raw tokens, email bodies, provider credentials,
   and provider exception text are excluded.
7. Production configuration fails closed unless the invitation secret is
   rotated, SMTP uses STARTTLS at a nonlocal endpoint, the sender is nonlocal,
   and the public application origin is nonlocal HTTPS.
8. Migration `20260727_0017` adds explicit terminal cancellation and a due-work
   partial index. Downgrade refuses while cancelled rows exist rather than
   fabricating a different terminal meaning.

## Consequences

- Invitation delivery survives scheduler, worker, and broker failures and can be
  reconciled from PostgreSQL without storing a bearer credential.
- SMTP cannot provide exactly-once external side effects. Duplicate email is
  possible after an ambiguous provider acknowledgement; the repeated link is
  intentionally identical and remains subject to exact account, expiry, status,
  and digest checks.
- A dead-letter row is an honest terminal failure. Reissuing or operator replay
  requires a separately authorized recovery workflow; this change does not add
  an unprotected replay endpoint.
- Existing module-specific workflow engines remain in place. Cross-workflow
  dashboards and alerts may aggregate safe status counts, but do not become a
  second state authority.

## Verification

- Domain tests cover deterministic token separation, fencing, replay, retry, and
  dead-letter transitions.
- Worker tests cover production configuration, queue routing, time limits,
  message escaping, safe failures, and operational-only task results.
- A real PostgreSQL integration test creates an invitation, claims and delivers
  it through the processor, persists delivery/audit state, and accepts the exact
  emitted credential.
- Migration `0017` is exercised upgrade, downgrade, re-upgrade, and with Alembic
  drift detection.
