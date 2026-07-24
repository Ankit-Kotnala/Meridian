# ADR 0014: Phase 8 Application Workspace and Grounded Packs

Status: Accepted
Date: 2026-07-24

## Context

Phase 8 connects saved jobs, immutable resume versions, evidence revisions, and
application activity. This creates a new integrity boundary: a later edit to a
job, resume, or evidence item must not silently rewrite what an application used,
and generated application material must not introduce or contradict factual
claims.

Application notes, contacts, tasks, interviews, offer details, and rejection
reasons are sensitive user-owned data. Board convenience must not weaken
authorization, concurrency, accessibility, or auditability. CareerOS does not
submit applications or send outreach on a user's behalf in the first production
release.

## Decision

Add `careeros.modules.application_workspace` as a bounded context with
owner-scoped application records, workflow events, tasks, notes, grounded packs,
consistency findings, idempotency records, and redacted audit events.

- Store the Phase 8 model in migration `20260724_0009`. Every child record carries
  explicit ownership and an application parent; repository reads scope by both
  owner and parent before returning a resource.
- Snapshot the selected Job Match version, source hash, typed requirement text and
  source spans, selected Resume Builder version, eligible evidence revisions and
  hashes, and claim-to-evidence/requirement links when an application is created
  or its resume version changes. Later source edits do not rewrite those pins.
- Consume job, resume, and evidence data only through explicit application query
  interfaces. The module does not query another bounded context's tables.
- Enforce the application stage state machine in the domain. Terminal records
  require an explicit reason to reopen. Mutable application and task writes use
  optimistic concurrency; retryable creates and pack generation use bounded
  idempotency keys.
- Generate pack documents deterministically from pinned, eligible claims. Each
  factual claim stores exact evidence-revision links and relevant job-requirement
  links. Unsupported numeric or factual material is blocked rather than rendered
  as plausible prose.
- Run a deterministic consistency pass across pinned job, resume, evidence, and
  every generated document. Blocking findings mark the pack and affected
  documents blocked; deletion preserves an audit trail without exposing deleted
  content.
- Expose purpose-minimized Phase 9 query views: interview preparation receives
  grounded claim and requirement context, while analytics receives workflow
  dimensions without notes, contacts, messages, or offer text.
- Keep FastAPI and Next.js adapters thin. Reads require an authenticated
  owner-scoped session; mutations require CSRF; responses containing workspace
  data use private no-store caching. The UI provides board, table, and calendar
  representations plus non-drag stage controls and complete loading, empty,
  success, failure, and conflict states.
- Do not add provider submission, email sending, social-network automation, or
  autonomous stage transitions. Generated messages are user-reviewed text only.

## Consequences

Applications remain reproducible even when their source job, resume, or evidence
changes later. The snapshot model duplicates a bounded amount of purpose-specific
text, but avoids historical drift and makes provenance machine-checkable.

The first Phase 8 pack generator is deterministic and synchronous while durable
idempotency, provenance, status, and audit data are persisted. A later provider or
worker implementation may improve wording or throughput only behind the same
schema, grounding, cost, retry, and consistency policies.

Board ordering is derived from persisted workflow fields rather than a separate
drag-only ordering model. This keeps keyboard and mobile controls authoritative
and avoids inaccessible or conflicting stage mutations.

## Clarification (2026-07-24)

The shipped Phase 6 migration `20260719_0007` remains immutable. Phase 8
migration `20260724_0009` forward-adds nullable `evidence_revision_id`,
`evidence_revision_number`, and `evidence_statement_sha256` columns to Change
Studio claims under an all-null or all-complete constraint. Existing claims
remain readable as explicitly unpinned history and are not backfilled from
current Career Record state. New claims require the complete tuple, while
Resume Builder and Application Workspace refuse an unpinned historical claim as
grounded generation input.

The immutable source ledger is exact, not an ID-only pointer. It records the job
ID/version/source SHA-256 and typed requirement spans; resume ID/immutable version
ID/version number after revalidating normalized claim hashes; and evidence ID/
revision ID/revision number/statement SHA-256. Creation reauthorizes current
eligibility and checks the referenced historical revision. An older resume or
Change Studio version without that complete ledger is not backfilled from today's
evidence and is refused as an application source.

A selected-resume change rebuilds the evidence snapshot and requires a
user-supplied reason. The workflow event and redacted audit entry preserve the
previous/next resume and evidence revision identifiers. This creates a new
auditable pin set; it never mutates the history of an earlier pack.

Application, task, note, event, and pack creates all use bounded idempotency keys
and request fingerprints. A client retains one key for one unchanged user intent,
including an ambiguous retry, and rotates it only after the relevant form changes
or the mutation succeeds. Reusing a key with different input is a conflict.

Application lists and child task/note/event/pack summaries use bounded opaque
cursor pagination. The application detail stays lightweight and the web loads
child panels on demand while retaining mounted draft state. This bounds query and
response growth without making hidden UI state an authorization control.

The deterministic synchronous generator and no-send/no-submit boundary are
intentional Phase 8 constraints, not placeholders for an unreviewed provider.
Any later language provider, durable worker, calendar/CRM connector, or delivery
tool must preserve these immutable inputs, grounding, stable idempotency,
ownership, audit, and explicit user-control decisions.
