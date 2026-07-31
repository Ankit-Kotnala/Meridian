# ADR 0022: Durable account privacy operations and classified cross-store erasure

- Status: Accepted
- Date: 2026-07-27
- Decision owners: Backend, platform, security, privacy, and release engineering
- Related: ADR 0005, ADR 0006, ADR 0007, ADR 0013, ADR 0019, ADR 0020, ADR 0021

## Context

CareerOS stores user-owned records in PostgreSQL and private files in
S3-compatible object storage. Account export and deletion therefore cannot be a
single synchronous SQL request. A process crash, worker redelivery, partial
object-store failure, organization ownership obligation, or billing-retention
obligation must not produce an untracked partial result or falsely report
completion.

The operation must remain inspectable after the user and their authenticated
session no longer exist. At the same time, security credentials, internal queue
state, other tenants' data, and object keys must not be disclosed in an export.

## Decision

1. Migration `20260727_0018` adds one durable `account_operations` state machine
   for export and deletion, with request/trace IDs, idempotency, attempt budget,
   retry time, UUID lease fencing, terminal timestamps, safe blocker/error codes,
   artifact integrity metadata, and a capability digest. The user foreign key
   becomes nullable with `ON DELETE SET NULL` so terminal state can survive
   erasure.
2. Export and deletion requests require an authenticated, CSRF-protected API
   call and an idempotency key. Deletion additionally requires recent
   authentication, disables the account, increments its auth version, revokes
   sessions and refresh tokens, and expires browser cookies immediately.
3. A context-separated deterministic HMAC capability authorizes only the named
   operation. Its secret is never stored or logged. The capability permits
   no-store status and short-lived download-grant requests after account
   deletion; knowing an operation UUID is insufficient.
4. The worker claims bounded due rows with `FOR UPDATE SKIP LOCKED` and an
   unexpired UUID lease. PostgreSQL/S3 work runs outside the row-lock
   transaction; only the terminal transition is locked and fenced. A deletion
   whose user row is already absent can be completed after a crash.
5. Export reflects the live PostgreSQL schema. Every direct user-linked table
   must be explicitly classified, owner-scoped, or explicitly internal. An
   unclassified table fails the operation closed. Authentication secrets,
   internal queues/idempotency state, object keys, and other tenants are
   excluded. Included files and table payloads carry SHA-256 integrity metadata
   in a bounded ZIP manifest.
6. Deletion inventories every known user-owned object reference, deletes objects
   idempotently, redacts prior account-export artifact metadata, and deletes the
   disabled user only after object deletion succeeds. PostgreSQL cascades or
   nulls classified user references. Retry and dead-letter state remains durable
   on failure.
7. A sole active organization owner is blocked until another active owner
   exists. An account with a billing-customer record is blocked pending
   provider/legal retention review. Blocked deletion restores the account;
   neither condition is silently bypassed.
8. Export artifacts default to 24-hour retention. Cleanup deletes the private
   object before redacting retained artifact metadata. Production rejects
   disabled privacy providers, the local capability secret, insecure object
   storage, or unsafe connection configuration.
9. Primary-store erasure does not claim immediate removal from backups or
   third-party providers. Backup expiry, provider deletion, legal retention, and
   user-facing disclosure remain explicit release-policy and operations work.

## Consequences

- Export and deletion are durable, retryable, auditable, tenant-safe, and
  inspectable without keeping an account or session alive.
- Schema growth cannot silently omit a new direct user-linked table; export
  fails until the table is classified.
- Cross-store atomicity is implemented as ordered, idempotent work rather than a
  fictitious distributed transaction. Object deletion precedes the user-row
  commit, so a retry may repeat deletes but cannot report success while a known
  primary object remains.
- Billing and sole-owner blockers are honest terminal policy outcomes. A future
  authorized workflow must resolve or supersede them; this ADR does not invent a
  payment-provider erasure policy.

## Verification

- Domain tests cover idempotent capability replay, recent-auth deletion,
  blocked-account restoration, retries, expiry cleanup, and delete-before-redact
  ordering.
- API and worker tests cover CSRF, idempotency, cookie expiry, capability-only
  status/download, no-store responses, safe aggregate task results, routing,
  schedules, limits, and production configuration.
- Real PostgreSQL/MinIO tests verify tenant-isolated ZIP content, password-secret
  exclusion, file integrity, user and object erasure, prior-export destruction,
  retained post-deletion operation status, sole-owner blocking, and
  billing-retention blocking.
- Migration `0018` passes upgrade, empty-state downgrade, re-upgrade, single-head
  graph checks, guarded fictional-seed checks, and Alembic drift detection.
