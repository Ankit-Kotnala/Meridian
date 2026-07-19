# ADR 0013: Phase 7 Resume Builder and Verified Export

Status: Accepted  
Date: 2026-07-19

## Context

Phase 7 turns grounded Career Record facts and Change Studio output versions into
downloadable resume files. This is a high-risk boundary because an exported PDF
or DOCX can look acceptable while losing text, changing order, duplicating
claims, or dropping evidence-backed details when parsed by another system.

The Career Record and evidence graph remain the source of truth. Resume Builder
must not invent facts, silently apply material changes, expose private object
keys, or let a client bypass grounding by editing generated prose directly.

## Decision

Add `careeros.modules.resume_builder` as a bounded context with structured resume
documents, immutable versions, deterministic rendering, round-trip verification,
private exported objects, download intents, idempotency records, and redacted
audit events.

- Store resumes, immutable versions, exports, verification reports, download
  intents, idempotency records, and audit events in migration `20260719_0008`.
- Build resume drafts only from owner-scoped Career Record eligibility snapshots
  and optional Change Studio current-version text through application contracts.
  Do not read another module's tables directly and do not accept arbitrary
  client-supplied evidence as grounding authority.
- Require every bullet to carry eligible evidence IDs. Server-side validation
  rejects unsupported edits instead of rendering them.
- Render five ATS-oriented templates to PDF, DOCX, plain text, and JSON from an
  immutable version. The local renderer favors searchable text and predictable
  reading order over decorative layout.
- Re-parse generated PDF/DOCX bytes before download. Critical missing bullets,
  evidence-bearing facts, duplicate bullet text, unreadable text, or grounding
  mismatches mark the export as blocked. Text and JSON exports receive the same
  structured verification policy without binary reparse.
- Issue only short-lived, owner-checked download intents for verified exports.
  The API never exposes internal object keys, and deletion removes the private
  export object plus the user-visible download path.
- Keep HTTP adapters thin: all reads are authenticated and owner-scoped;
  mutations require CSRF; retryable exports and download-intent creation require
  idempotency keys; mutable resume writes use ETags/`If-Match`.

## Consequences

The first Phase 7 vertical slice executes rendering and verification immediately
inside the application service while persisting job state, attempts, hashes,
warnings, failures, and dead-letter metadata. That keeps the workflow complete
and deterministic locally, with a clear extraction point for a Celery renderer
when production scale requires queue isolation.

Templates are intentionally constrained. Rich multi-column or graphics-heavy
designs wait until they can prove searchable, stable round-trip output. Users
can restore prior immutable versions, but exported bytes remain pinned to the
version and hash that passed verification.
