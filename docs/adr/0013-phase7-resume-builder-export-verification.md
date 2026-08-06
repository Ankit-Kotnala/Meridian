# ADR 0013: Phase 7 Resume Builder and Verified Export

Status: Accepted  
Date: 2026-07-19
Amended: 2026-07-26

## Context

Phase 7 turns grounded Career Record facts and Change Studio output versions into
downloadable resume files. This is a high-risk boundary because an exported PDF
or DOCX can look acceptable while losing text, changing order, duplicating
claims, or dropping evidence-backed details when parsed by another system.

The Career Record and evidence graph remain the source of truth. Resume Builder
must not invent facts, silently apply material changes, expose private object
keys, or let a client bypass grounding by editing generated prose directly.

## Decision

Add `rezumi.modules.resume_builder` as a bounded context with structured resume
documents, immutable versions, deterministic rendering, round-trip verification,
private exported objects, download intents, idempotency records, and redacted
audit events.

- Store resumes, immutable versions, exports, verification reports, download
  intents, idempotency records, and audit events in migration `20260719_0008`.
  Add structured layout/fact pins, durable render outbox state, exact fidelity
  fields, and fenced private-object cleanup through additive migrations
  `20260726_0012` and `20260726_0013`.
- Build resume drafts only from owner-scoped Career Record eligibility snapshots
  and optional Change Studio current-version text through application contracts.
  Do not read another module's tables directly and do not accept arbitrary
  client-supplied evidence as grounding authority.
- Require every bullet to carry eligible evidence IDs. Server-side validation
  rejects unsupported edits instead of rendering them.
- Render five genuinely distinct, constrained ATS-oriented templates to PDF,
  DOCX, plain text, and JSON from an immutable version. Page size, one/two-page
  limit, font family/size, spacing, and margins are pinned with that version.
  The local renderer embeds a Unicode-capable font and favors searchable text
  and predictable reading order over decorative layout.
- Build one canonical `career-resume-fidelity-v1` manifest for every format and
  pin both the complete version hash and manifest hash when export is accepted.
  Re-parse generated PDF/DOCX bytes independently. Exact omissions,
  duplications, order changes, searchability failures, page-limit overflow,
  unsupported factual content, ungrounded numbers, or pin drift block release
  and delete the failed object. Text and JSON use the same manifest policy.
- Accept export and deletion requests quickly by persisting state plus an
  operation-typed transactional outbox. Celery receives only the export UUID,
  trace ID, and allowlisted `render`/`delete` operation. Workers claim fenced
  leases, retry with bounded backoff, dead-letter terminal failures, and are
  recovered by a periodic reconciler. Duplicate or stale delivery cannot
  overwrite a newer lease.
- Commit an owner-scoped, attempt-fenced object-cleanup backstop in the same
  transaction that claims each render lease, before any object-store write.
  Each attempt uses a distinct key. The verified winner cancels its backstop
  atomically with export completion; crashes, uncertain writes, failed
  verification, and stale attempts remain safely deletable by bounded
  reconciliation with explicit retry/dead-letter state.
- Issue only short-lived, owner-checked download intents for verified exports.
  The API never exposes internal object keys, and deletion removes the private
  export object plus the user-visible download path.
- Keep HTTP adapters thin: export and deletion return `202` durable state for
  reload-safe polling; all reads are authenticated and owner-scoped;
  mutations require CSRF; retryable exports and download-intent creation require
  idempotency keys; mutable resume writes use ETags/`If-Match`.

## Consequences

Rendering, independent extraction, verification, failed-object cleanup, and
explicit export deletion run only in the isolated worker; the API no longer
holds those CPU- and parser-heavy responsibilities. Database state is truthful:
`deleted_at` is set only after the private object delete succeeds. Storage or
broker outages remain visible as retry/dead-letter states and retain enough
durable state for safe operator recovery without logging resume content.
Migration `20260726_0013` returns inconsistent legacy `deleted` rows to durable
deletion instead of erasing their object key or fabricating a deletion time.

Templates remain intentionally single-column-first and constrained. Rich
graphics-heavy designs wait until they can pass the same exact manifest corpus.
Users can autosave, undo/redo locally, compare or restore immutable history, and
preview layouts, but every server-accepted factual bullet still comes from an
eligible source. Exported bytes remain pinned to the exact version and hashes
that passed verification.
