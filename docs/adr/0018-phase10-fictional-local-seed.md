# ADR 0018: Production-Guarded Fictional Local Seed

Status: Accepted
Date: 2026-07-26

## Context

CareerOS now has durable product models across Phases 1 through 9 and private
objects in MinIO. The original `make seed` only printed a Phase 0 presentation
fixture. That behavior could not exercise ownership, provenance, immutable
version pins, analytics suppression, object references, migrations, or local
development workflows.

A cross-phase seed is unusually risky. Running it against a shared or production
database could create a known login, synthetic personal data, misleading audit
history, or object references that look real. Replaying a naive seed could
overwrite developer edits or duplicate immutable versions. Reusing an API route
would expose development tooling in a delivery surface, while importing one
product module's persistence from another would violate module boundaries.

## Decision

Add a separate `careeros.development.local_seed` tooling composition root and a
Compose `tools` profile. It is not imported by the API or worker application,
has no HTTP/task route, and does not start with the normal platform.

Before dependency I/O, the command requires all of the following:

- explicit `development` environment;
- an exact non-secret confirmation value supplied by `make seed` or the checked
  PowerShell wrapper;
- the local `careeros` database identity and database name on the Compose
  `postgres` alias or a loopback host;
- a path-free local MinIO endpoint and the private `careeros-documents` bucket;
- matching URL/SSL settings; and
- the exact reviewed Alembic migration head.

The seed uses UUIDv5 identifiers in a dedicated namespace, fixed fictional
timestamps, reserved `.invalid` email addresses, conspicuous fictional labels,
the existing CareerOS-authored role taxonomy, and no external content. It
creates a valid graph spanning Identity, Resume Health, Career Record, Role
Explorer, Job Match, Change Studio, Resume Builder, Application Workspace, and
the four Phase 9 contexts.

Factual fixture text follows the same source-of-truth chain as product data:
reviewed source span to confirmed evidence revision, Change Studio claim,
immutable resume version, verified export, and pinned application/interview
context. Analytics output uses the canonical non-causal interpretation and
small-cohort suppression.

Rows use PostgreSQL `ON CONFLICT DO NOTHING` on their primary keys. Existing
mutable rows are preserved. Immutable fixture rows are compared before object
writes and again after the transaction; drift fails safely instead of being
overwritten. Both private objects use deterministic keys and bytes, are written
idempotently, then read back and byte-compared before success. The fresh local
login value is printed only on first account creation and is explicitly public
fixture data, not a secret or reusable credential.

Direct table inserts are permitted only in this outer development composition
root. Product modules remain isolated and continue to communicate through
application interfaces at runtime. Database constraints and domain constructors
remain executable validation, while a migration-head pin forces an explicit
seed review whenever the schema changes.

## Consequences

- Local development can start from a coherent, visibly fictional end-to-end
  graph without weakening product APIs or authorizing production writes.
- Replaying the seed is non-destructive and does not silently reset edited local
  state.
- A schema migration intentionally breaks the seed gate until the manifest and
  expected head are reviewed together.
- Database and object-store availability are required for the final seed gate.
  Pure tests and Compose configuration are useful evidence but do not replace a
  two-run PostgreSQL/MinIO verification.
- This command is not a production bootstrap, backup restore, data migration,
  demo-account provider, or source of real career claims.
