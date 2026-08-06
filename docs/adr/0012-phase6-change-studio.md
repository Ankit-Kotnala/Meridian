# ADR 0012: Phase 6 Change Studio and Truth-Locked AI

Status: Accepted  
Date: 2026-07-19

## Context

Phase 6 introduces generated resume-change suggestions without weakening the
Rezumi source-of-truth rule. The inputs are owner-scoped Career Record evidence
and saved Job Match requirement snapshots. Provider output, job descriptions, and
user edits remain hostile until deterministic validation proves each factual
claim is grounded.

## Decision

Add `rezumi.modules.change_studio` as a bounded context with strict provider
schema parsing, deterministic grounding, owner-scoped application use cases,
SQLAlchemy persistence, and thin FastAPI/Next.js adapters.

- Store change sets, structured operations, claim-ledger entries, clarifying
  questions, immutable versions, provider-run metadata, idempotency records, and
  redacted audit events in migration `20260719_0007`.
- Consume evidence only through Career Record eligibility queries and job
  requirements only through Job Match application views. Do not read another
  module's tables or trust client-submitted evidence IDs.
- Route suggestions through an environment-selected provider gateway. Local and
  test environments use a deterministic provider that only reuses eligible
  evidence text; production must configure an HTTPS JSON provider with an API key
  or explicitly disable the feature.
- Treat every provider payload as untrusted JSON. Unknown fields, invalid IDs,
  unsafe text, unsupported facts, ungrounded numbers, prompt-injection text, and
  cross-owner evidence/requirements fail closed or become neutral clarifying
  questions.
- Require authentication for all Change Studio reads, CSRF for mutations,
  idempotency keys for side effects, `If-Match` for versioned writes, and an
  explicit user action before material changes alter the current version.
- Preserve immutable version history and audit accept/reject/edit/alternate,
  lock/unlock, undo/redo, restore, and clarification-answer actions.

## Consequences

Change Studio can ship without third-party AI credentials while keeping the
provider boundary production-ready. The deterministic provider is conservative:
it cannot discover useful paraphrases beyond eligible evidence already matched by
Job Match. Remote providers improve wording only after security, privacy, data
residency, retention, cost, and model-output validation controls are configured.

The Phase 6 current version is a Change Studio output version, not yet a full
exportable resume document. Phase 7 will integrate these immutable versions with
resume editing, rendering, round-trip verification, and download controls.
