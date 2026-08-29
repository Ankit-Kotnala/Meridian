# Rezumi API conventions and route plan

Status: Phase 8 and Phase 9 APIs complete and hosted verified
Base path for product APIs: `/api/v1`  
Last reviewed: 2026-07-25

## Implementation truth

The API's generated OpenAPI document is authoritative for implemented request and
response shapes. This document defines conventions and the intended route map.
A route listed as a future phase is not implemented merely because it appears
here.

### Implemented foundation endpoints

| Method | Path           | Purpose                                                                       | Dependency behavior                                                        |
| ------ | -------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `GET`  | `/health`      | API process liveness                                                          | Does not require downstream services                                       |
| `GET`  | `/ready`       | API readiness                                                                 | Probes configured PostgreSQL, Redis, SMTP, and object-storage dependencies |
| `GET`  | `/api/v1/meta` | Safe service name/version/environment and canonical internal-score disclaimer | No secret or detailed topology                                             |

The web separately exposes `GET /api/health` for its own liveness on port 3000.
It is not part of the product API contract.

Phase 1 adds persisted identity, account, consent, session, and onboarding
resources. Phase 2 adds owned and guest-limited resume upload, parsing, review,
analysis, and deletion resources. Phase 3 adds account-owned career profile,
evidence, attachment, proposal, and achievement resources. Phase 4 adds role
taxonomy/search, saved roles, deterministic readiness analysis, history, and
comparison. Phase 5 adds authenticated job posting save/import, requirement
matrix analysis, and opportunity priority. Phase 6 adds authenticated Change
Studio change sets, truth-locked provider suggestions, grounding decisions,
clarifying questions, and immutable output versions. Phase 7 adds authenticated
structured resumes, immutable resume versions, verified PDF/DOCX/text/JSON
exports, round-trip reports, short-lived download intents, and export deletion.
Phase 8 adds authenticated applications, stage/outcome/task/note/event tracking,
bounded calendar/list views, exact immutable source pins, deterministic grounded
application packs, consistency results, and deletion. It deliberately adds no
application-submission or message-sending route. `/docs` and `/openapi.json` are
development documentation endpoints and may be restricted or disabled in
production.

Phase 9 adds authenticated Interview Prep, Networking, Career Growth, and Career
Analytics operations. Interview and Growth consume exact owner-authorized
evidence through application interfaces. Networking owns separate contact
consent and local-only reminder state. Analytics uses durable jobs and immutable
timezone-specific snapshots without accepting raw career/contact prose. No Phase
9 route sends a message, imports or scrapes contacts, changes an external system,
or submits an application.

`shared/contracts` derives its public types and client from the implemented
FastAPI OpenAPI document. The normalized artifact under
`shared/contracts/openapi` and generated files under
`shared/contracts/src/generated` are committed review artifacts; neither is an
independent contract authority. Problem, pagination, and product schemas are not
published until corresponding Pydantic models and operations exist. Phase 1
contract evidence is recorded in `PLANS.md`. Phase 2 through Phase 9 changes
regenerate both artifacts; the final drift result must be recorded there before a
phase is marked complete.

## Protocol and representation

- Production uses HTTPS only; JSON is UTF-8 unless an explicitly documented file
  response says otherwise.
- Product clients call `/api/v1`. Health probes remain unversioned.
- Resource IDs are UUID strings. Timestamps are UTC RFC 3339 with offset (`Z`
  preferred). Full dates without time use ISO 8601 calendar dates. Career Record
  manual writes use `YYYY-MM`; imported responses may preserve `YYYY` or
  `YYYY-MM` and never invent a day.
- Money uses a decimal string plus ISO 4217 currency, never binary float. Locale-
  formatted text is display-only.
- Unknown request fields are rejected for sensitive write schemas unless a
  versioned extension policy explicitly permits them.
- Clients send `Accept: application/json`; writes send
  `Content-Type: application/json`. Problem responses use
  `application/problem+json` where practical.
- Field names use lower camel case on the wire. Python/internal/database naming
  may differ through explicit aliases.
- Responses never include secrets, hashes of authentication tokens, internal
  object keys, raw stack traces, provider credentials, or another tenant's IDs.

## Request context and headers

| Header                   | Direction         | Rule                                                                                                     |
| ------------------------ | ----------------- | -------------------------------------------------------------------------------------------------------- |
| `X-Request-ID`           | request/response  | Client may supply a bounded safe value; edge replaces invalid values and always returns the effective ID |
| `traceparent`            | request/internal  | Valid W3C context is propagated; invalid input starts a new trace and is never trusted for authorization |
| `X-Trace-ID`             | response/internal | Effective 32-hex trace ID returned by the Phase 0 API and bound to structured logs; diagnostic only      |
| `Idempotency-Key`        | request           | Required where specified; 8-128 characters from `[A-Za-z0-9._:-]`                                        |
| `If-Match`               | request           | Required where specified; quoted positive integer version, maximum `2147483647`                          |
| `ETag`                   | response          | Represents a mutable resource version, not a secret                                                      |
| `X-CSRF-Token`           | request           | Phase 1 cookie-authenticated state-changing request defense, paired with origin policy                   |
| `X-Guest-CSRF`           | request           | Phase 2 guest double-submit token, paired with the guest capability cookie and origin policy             |
| `X-Rezumi-Client-Signal` | internal request  | HMAC-authenticated opaque per-source input from the trusted web BFF; never authorization                 |
| `Retry-After`            | response          | Returned for applicable `429` or temporary `503` responses                                               |

Correlation IDs are safe opaque diagnostics. They are shown in user-facing errors
and logs but never grant access.

HTTP completion and failure logs use the matched route template (or the literal
`unmatched`) rather than a raw path/query. They include only allowlisted request
metadata and, on failure, the exception class; request/response bodies, exception
messages, headers, signed URLs, and resume text are excluded. Payload-bearing
library access loggers are disabled in favor of these structured events. An
unexpected exception is converted there into a generic no-store `internal_error`
problem, so its message/traceback is not re-raised into the ASGI server logger.

## Authentication and authorization (implemented through Phase 2)

The browser uses API-owned secure HTTP-only session/refresh cookies. JavaScript
does not persist bearer or refresh tokens in local storage. State-changing routes
require CSRF protection and an allowed origin. Google OAuth uses state, nonce,
PKCE, and exact redirect URIs.

Session and one-time secrets are opaque and stored only as keyed hashes. Refresh
tokens rotate on use; reuse revokes the token family. Passwords use Argon2id.
Verification/recovery responses and abuse limits do not disclose whether an email
exists. The web reaches these endpoints through an allowlisted same-origin
`/api/v1/*` proxy and never accepts an arbitrary upstream target.
See ADR 0008 for the implemented session and web/API boundary decision.

In local Compose, only `web-edge` publishes the web port. It removes every
client-selected address header, writes `X-Forwarded-For` from the socket peer,
and forwards to the unexposed Next.js service. The server-side BFF normalizes
that address and signs it with a server-only secret; the API verifies the signal
before using its opaque signature as a pre-authentication/first-guest upload rate
subject. The source key is deliberately neutral: it grants no session, guest
capability, tenant, or resource access. Direct browser input cannot supply the
internal signal. A deployment behind a cloud load balancer needs an explicit
allowlisted trusted-hop policy, because the local edge otherwise sees only the
balancer.

Every user-owned lookup is scoped by authenticated user and current tenant in the
service/repository query. Tenant selection is validated against membership; a
client-supplied tenant header or resource UUID is not authorization. Background
jobs and signed-object operations repeat ownership checks.

Expected authorization outcomes:

- `401` when no valid principal exists;
- `403` when the principal is known but lacks a capability;
- `404` is preferred for inaccessible user-owned resources where revealing
  existence would aid enumeration;
- `409` for state/version/idempotency conflicts.

Admin endpoints use a separate explicit capability model and audit sensitive
reads/writes. Admin status never grants unbounded raw resume access.

## Standard problem response

Errors are stable, safe, and actionable without exposing internals:

```json
{
  "type": "https://rezumi.example/problems/validation-error",
  "title": "Request validation failed",
  "status": 422,
  "code": "validation_error",
  "detail": "Review the highlighted fields.",
  "instance": "/api/v1/experiences",
  "requestId": "01J...",
  "errors": [
    {
      "field": "startDate",
      "code": "invalid_date",
      "message": "Use an ISO 8601 calendar date."
    }
  ]
}
```

`detail` and field messages are safe for the authenticated user and localization.
They do not echo raw document/job text, secret/token values, parser stack traces,
SQL, provider responses, or internal addresses. Machine behavior keys on `code`,
not English prose.

Common codes include `validation_error`, `authentication_required`, `forbidden`,
`not_found`, `version_conflict`, `idempotency_conflict`, `rate_limited`,
`payload_too_large`, `unsupported_document`, `dependency_unavailable`,
`processing_failed`, `grounding_failed`, and `internal_error`.

## Collections, filtering, and sorting

Growing collections use opaque cursor pagination:

```http
GET /api/v1/evidence?limit=25&after=opaqueCursor&state=confirmed&sort=-updatedAt
```

```json
{
  "data": [],
  "page": {
    "limit": 25,
    "nextCursor": null,
    "hasMore": false
  }
}
```

- Default and maximum `limit` are server configuration with documented bounds.
- Cursors encode no trusted authorization; ownership is rechecked on every page.
- Filters and sort fields are endpoint-specific allowlists. Unknown fields return
  validation errors. Search strings and date ranges are bounded.
- Responses do not expose a cross-tenant total. A count is returned only when the
  endpoint can compute it safely and usefully.

Small version/history collections may use bounded page-number pagination if the
OpenAPI contract explicitly says so.

## Idempotency and concurrency

The implemented Resume Health `Idempotency-Key` accepts 8 through 128 ASCII
characters and only letters, digits, dot, underscore, colon, or hyphen. Finalize,
analysis, cancellation, and deletion validate that form. Canonical correction
and deletion use `If-Match` as a quoted positive integer no greater than
PostgreSQL `int4` maximum `2147483647`; zero, signs, whitespace, weak ETags, and
larger values are rejected at the transport boundary.

Important retryable `POST`s—analysis, import, change-set generation, export,
application-pack generation, webhook processing, data export/deletion, and safe
job retry—require `Idempotency-Key`.

The API stores a scoped key with authenticated subject/tenant, route/operation,
canonical request hash, state, and response reference for a bounded period:

- same key and same request returns/references the original operation;
- same key with a different request returns `409 idempotency_conflict`;
- concurrent duplicate requests converge on one durable operation;
- a key never deduplicates across users or tenants.

Mutable aggregate APIs expose a `version` and/or ETag. Update/delete with stale
`If-Match` returns `409 version_conflict` (or `412` if the OpenAPI contract adopts
strict HTTP precondition semantics consistently) plus safe refetch guidance.
Immutable resume versions and exports are never updated in place.

## Asynchronous operation model

Long-running endpoints return `202 Accepted` with a durable operation reference:

```json
{
  "job": {
    "id": "7bfe7c12-61ec-4b50-9ec7-69f7a01112bc",
    "type": "resume_health",
    "status": "queued",
    "progress": null,
    "createdAt": "2026-07-14T08:00:00Z",
    "statusUrl": "/api/v1/processing-jobs/7bfe7c12-61ec-4b50-9ec7-69f7a01112bc"
  }
}
```

Status is one of `queued`, `running`, `succeeded`, `failed`, or `cancelled`.
`progress`, when available, is a bounded percentage plus a safe stage code—not
raw parser/provider output. Successful jobs link to an authorized result. Failed
jobs expose a safe error code, retryability, and request ID. Retrying creates or
references an idempotent job according to policy.

Workers receive IDs and trace context rather than raw credentials or entire
documents in queue payloads. Every task reloads ownership and state, defines a
timeout and bounded retries, records progress/cost where useful, and routes poison
work to dead-letter handling.

Resume processing adds a hash of a fresh per-invocation delivery token and a
durable lease whose duration exceeds the worker hard timeout. A duplicate that
finds a live lease returns the safe `execution_lease_active` state and schedules
a delayed retry after that lease must have expired. A successor may reclaim an
expired lease within the durable attempt cap; every progress/result write checks
the token, so the stale invocation cannot commit afterward. Job creation and its
outbox row are transactional. The outbox publisher and object-cleanup maintenance
both use caller-bounded batches (1-500), bounded attempts/backoff, and explicit
dead-letter state.

Polling is the initial completion mechanism. Server-sent events or notifications
may be added as a separate authenticated contract after need is demonstrated.

## Upload contract (Phase 2)

The implemented direct-upload sequence is:

1. The client reads the account or guest upload-policy endpoint and validates PDF
   or DOCX filename, media type, and size locally for immediate feedback.
2. `POST /api/v1/uploads/presign` (or its `/guest` equivalent) supplies display
   filename, exact expected byte count, media type, and purpose
   `resume_health`.
3. The API applies owner/guest quota and rate policy, persists a short-lived
   intent, and returns a signed `PUT` for a randomized `staging/` key. The
   browser accepts that URL only when its origin equals the configured upload
   origin and sends no application credentials to object storage.
4. The client transfers bytes directly with the exact signed headers and reports
   real byte progress. No permanent object credentials or standalone/unsigned
   object-key field is returned; the randomized staging key is exposed only as
   part of the short-lived, operation-scoped signed URL.
5. `POST .../uploads/{uploadId}/finalize` rechecks scope, expiry, object size,
   object media type, and file signature. It promotes the object to a randomized
   `quarantine/` key, creates an owned document plus parse job and transactional
   outbox row, and returns `202`.
6. The web polls the owned job/document resources. Only the worker can mark a
   document clean and review-ready after malware and parser admission.

Browser filename, extension, MIME, object metadata, and upload completion are
untrusted. See `docs/security-threat-model.md`.

The upload-policy `maxPages` value is an authoritative PDF limit in the local
extractor. `python-docx` cannot reliably infer rendered DOCX pages, so DOCX is
bounded instead by upload bytes, archive entries, expanded bytes/ratio, extracted
characters/blocks, artifact size, and worker resources. The locally reported
DOCX page value is nominal and must not be presented as a rendered-page claim.

The web retains a successfully issued intent, transfer state, and finalize
idempotency key only in memory while the upload component remains mounted. It can
retry an ambiguous transfer/finalize without requesting another intent. A page
reload or lost intent response cannot recover that state: the intake may count
toward quota for up to the default five-minute intent TTL. Scheduled cleanup
later removes any orphaned staging bytes. The Phase 2 protocol is a single signed
`PUT`; it does not provide resumable or multipart transfer.

## Route inventory by phase

The methods below are the implemented public surface through Phase 9 and the
current cross-phase closure, followed by explicitly labeled planned surfaces.
The generated OpenAPI artifact remains authoritative. Future planned names may be
refined through OpenAPI review; released methods follow the compatibility rules.

### Phase 1 — Authentication, account, and onboarding

```text
POST   /api/v1/auth/register
GET    /api/v1/auth/csrf
POST   /api/v1/auth/verify-email
POST   /api/v1/auth/resend-verification
POST   /api/v1/auth/login
POST   /api/v1/auth/logout
POST   /api/v1/auth/logout-all
POST   /api/v1/auth/refresh
POST   /api/v1/auth/forgot-password
POST   /api/v1/auth/reset-password
POST   /api/v1/auth/change-password
GET    /api/v1/auth/sessions
DELETE /api/v1/auth/sessions/{sessionId}
GET    /api/v1/auth/google/start
GET    /api/v1/auth/google/callback
DELETE /api/v1/auth/connections/google
GET    /api/v1/me
PATCH  /api/v1/me
GET    /api/v1/onboarding
PATCH  /api/v1/onboarding
GET    /api/v1/consents
POST   /api/v1/consents
GET    /api/v1/settings
GET    /api/v1/security-activity
```

Registration/login/reset responses resist account enumeration. OAuth callback
errors return through a safe fixed application route without leaking provider
tokens. `GET` responses for `/me` and `/onboarding` return versions/ETags; their
`PATCH` operations require CSRF plus `If-Match`. Onboarding upload, processing,
typed-review, and analysis statuses are server-observed through an owner-scoped
Resume Health application query; the mutation cannot submit them. Password
changes and Google disconnection require CSRF and recent authentication. A
successful password change revokes all sessions, including the current one.
Security activity returns a bounded owner-scoped redacted view. `GET /settings`
returns persisted account-security state plus fail-closed capability flags; it
does not imply that export, account deletion, billing, or scheduled notification
delivery exists. Account deletion remains Phase 10 work and will require recent
authentication.

### Phase 2 — Upload, documents, parsing, and Resume Health

```text
GET    /api/v1/resume-health/upload-policy
POST   /api/v1/uploads/presign
POST   /api/v1/uploads/{uploadId}/finalize
GET    /api/v1/documents
GET    /api/v1/documents/{documentId}
GET    /api/v1/documents/{documentId}/status
GET    /api/v1/documents/{documentId}/plain-text
GET    /api/v1/documents/{documentId}/reading-order
PATCH  /api/v1/documents/{documentId}/canonical-resume
DELETE /api/v1/documents/{documentId}
POST   /api/v1/resume-health
GET    /api/v1/resume-health/{analysisId}
GET    /api/v1/processing-jobs/{jobId}
POST   /api/v1/processing-jobs/{jobId}/cancel

GET    /api/v1/guest/resume-health/upload-policy
POST   /api/v1/guest/uploads/presign
POST   /api/v1/guest/uploads/{uploadId}/finalize
GET    /api/v1/guest/documents/{documentId}
GET    /api/v1/guest/documents/{documentId}/status
GET    /api/v1/guest/documents/{documentId}/plain-text
GET    /api/v1/guest/documents/{documentId}/reading-order
PATCH  /api/v1/guest/documents/{documentId}/canonical-resume
DELETE /api/v1/guest/documents/{documentId}
POST   /api/v1/guest/documents/{documentId}/claim
POST   /api/v1/guest/resume-health
GET    /api/v1/guest/resume-health/{analysisId}
GET    /api/v1/guest/processing-jobs/{jobId}
POST   /api/v1/guest/processing-jobs/{jobId}/cancel
```

Account resources are scoped by the authenticated Phase 1 principal in every
service/repository lookup. Inaccessible IDs return the same safe not-found class.
Canonical correction and deletion require `If-Match`; upload finalize, analysis,
deletion, and job cancellation require an `Idempotency-Key` where defined by
OpenAPI. Parse/analyze cancellation is cooperative; delete jobs reject
cancellation because partial erasure must continue to a durable terminal state.

Guest routes use a narrow, opaque capability in the path-restricted, `HttpOnly`,
`SameSite=Lax` `rezumi_guest_capability` cookie. Mutations also require an
exact allowed origin and `X-Guest-CSRF` matching the readable guest CSRF cookie.
A guest may have one active intake and the default capability/document retention
is 24 hours (bounded by configuration to seven days). The browser never submits a
user or tenant ID as guest authorization. Claiming requires a valid guest
capability, an authenticated account session, CSRF, and explicit consent; the
service rechecks account quota, copies objects to new account-owned randomized
keys, requires a ready document with completed analysis and no active/retryable
job, transfers retained content/job history atomically, removes guest retention,
and revokes the guest capability. Prior guest audit records retain their original
scope while the claim adds a new account-scoped audit event.

Canonical responses retain immutable source sections/blocks and expose a
versioned semantic sidecar for contact, experience, education, project, skill,
and certification records. Parser-derived fields carry confidence, review state,
date precision where applicable, and exact block/page/character/SHA-256 anchors.
The patch contract accepts discriminated confirm, correct, add, remove, and
reclassify operations, or an explicit no-change confirmation. User-added facts
make no source-anchor claim. Every accepted review creates an optimistic,
immutable successor snapshot; legacy block-only snapshots upgrade through that
same explicit path and the source document is never overwritten.

Analysis binds to one snapshot and returns fixed-point score/components,
engine/configuration/feature-schema versions, all persisted feature values, each
component's feature score/weight/contribution in raw basis points and display
units, feature hash, findings, warnings, and the canonical disclaimer. Current
Resume Health v2 includes semantic breadth, source-anchor coverage, explicit
review coverage, and date-precision coverage. The web exposes that trace in
keyboard-operable disclosure lists. Insufficient extracted data returns no
numeric score rather than zero.

Delete is a durable background operation. The worker removes the quarantined
object and derived artifacts, purges canonical/analysis content, and retains a
minimal redacted document/job/audit record. Scheduled retention uses the same
durable delete path before revoking an expired guest capability.

### Phase 3 — Career profile, evidence, and achievements

```text
GET    /api/v1/career-profile
PATCH  /api/v1/career-profile

GET    /api/v1/personal-facts
POST   /api/v1/personal-facts
PATCH  /api/v1/personal-facts/{factId}
POST   /api/v1/personal-facts/{factId}/confirm
DELETE /api/v1/personal-facts/{factId}

GET    /api/v1/experiences
POST   /api/v1/experiences
PATCH  /api/v1/experiences/{experienceId}
POST   /api/v1/experiences/{experienceId}/confirm
DELETE /api/v1/experiences/{experienceId}
POST   /api/v1/experiences/reorder

GET    /api/v1/career-items
POST   /api/v1/career-items
PATCH  /api/v1/career-items/{careerItemId}
POST   /api/v1/career-items/{careerItemId}/confirm
DELETE /api/v1/career-items/{careerItemId}

GET    /api/v1/skills
POST   /api/v1/skills
PATCH  /api/v1/skills/{skillId}
POST   /api/v1/skills/{skillId}/confirm
DELETE /api/v1/skills/{skillId}

GET    /api/v1/career-relationships
POST   /api/v1/career-relationships
DELETE /api/v1/career-relationships/{relationshipId}

POST   /api/v1/career-profile/semantic-import-proposals
GET    /api/v1/career-profile/semantic-import-proposals
GET    /api/v1/career-profile/semantic-import-proposals/{proposalId}
POST   /api/v1/career-profile/semantic-import-proposals/{proposalId}/accept
POST   /api/v1/career-profile/semantic-import-proposals/{proposalId}/reject

GET    /api/v1/career-profile/import-proposals
POST   /api/v1/career-profile/import-proposals  (deprecated creation path)
GET    /api/v1/career-profile/import-proposals/{proposalId}
POST   /api/v1/career-profile/import-proposals/{proposalId}/accept
POST   /api/v1/career-profile/import-proposals/{proposalId}/reject

GET    /api/v1/evidence
POST   /api/v1/evidence
GET    /api/v1/evidence/{evidenceId}
PATCH  /api/v1/evidence/{evidenceId}
DELETE /api/v1/evidence/{evidenceId}
POST   /api/v1/evidence/{evidenceId}/confirm
POST   /api/v1/evidence/{evidenceId}/unsupported
POST   /api/v1/evidence/{evidenceId}/archive
POST   /api/v1/evidence/{evidenceId}/restore
GET    /api/v1/evidence/{evidenceId}/usage

POST   /api/v1/evidence/{evidenceId}/attachments/presign
POST   /api/v1/evidence/{evidenceId}/attachments/{uploadId}/finalize
GET    /api/v1/evidence/{evidenceId}/attachments/{attachmentId}/download
DELETE /api/v1/evidence/{evidenceId}/attachments/{attachmentId}
POST   /api/v1/evidence/{evidenceId}/conflicts/{conflictId}/resolve

GET    /api/v1/achievements
POST   /api/v1/achievements
GET    /api/v1/achievements/reminder-preferences
PATCH  /api/v1/achievements/reminder-preferences
GET    /api/v1/achievements/{achievementId}
PATCH  /api/v1/achievements/{achievementId}
DELETE /api/v1/achievements/{achievementId}
POST   /api/v1/achievements/{achievementId}/confirm
```

Typed semantic proposal creation takes an owned Resume Health document ID and
loads its reviewed immutable semantic snapshot server-side. Only confirmed,
corrected, or explicit user-added fields are candidates. Accepting a proposal
creates or updates canonical personal facts, skills, experiences, education,
projects, or certifications and records canonical per-field provenance; an
accept-time edit is labeled as an owner edit rather than parser text. Manual and
edited records require explicit confirmation, and material edits revoke prior
confirmation. Downstream readiness snapshots exclude unconfirmed records and
include confirmed personal facts for document-generation consumers.

Career relationships currently allow an explicit owned experience-to-project
edge. Achievement-to-entity and evidence-to-entity/skill links remain in their
existing canonical structures. The legacy generic proposal creation method is
retained and marked deprecated for v1 compatibility and historical audit; new UI
uses the typed route.

All Phase 3 routes require the Phase 1 authenticated account session. Mutations
also require the session-bound CSRF/origin contract; versioned writes require a
strict quoted positive-int32 `If-Match` where exposed. The service fetches by
owner plus resource ID, validates nested links in the same scope, and deliberately
returns the same not-found result for unknown and cross-user IDs.

Career items cover education, projects, certifications, awards, volunteering,
publications, and languages. Experience supports explicit grouping with an owned
peer; the server classifies overlapping same-employer roles as a promotion
sequence and different-employer overlap as concurrent work. Reorder validates
the complete owned set. Resume imports create a pending, source-preserving
proposal only; accept/edit-and-accept/reject are explicit versioned decisions and
never overwrite career truth silently.

Evidence transition endpoints enforce lifecycle and strength server-side and
emit redacted audit history. Manual and URL sources start Inferred; exact validated
resume spans can start Supported; `confirm` creates Confirmed only after the
required claim and numeric dimensions pass. No verification authority is
configured, so production APIs cannot create Verified and never trust a client-
supplied state. Archive is reversible but ineligible; material edit creates an
immutable successor and invalidates prior confirmation. External URL provenance
is stored and validated as HTTP(S) metadata only—Phase 3 does not fetch it.

For a legacy whole-block resume source, the submitted description must match the
immutable original block byte-for-byte after boundary whitespace removal. The
server derives its title and rejects additional type, context, organization/
project, date, metric, entity-link, or skill-link scope. Any mismatch returns the
redacted `career_record_source_unavailable` problem before evidence or audit
persistence. Live eligibility rechecks persisted exact claims and returns
`supported_scope_mismatch` for a spoofed or drifted legacy row while preserving
its immutable history.

The evidence response includes server-authoritative factual/numeric eligibility,
reason codes, provenance, immutable history, conflicts, attachments, links, and
downstream usage. Inferred, Unsupported, archived, deleted, conflicted,
unauthorized, and unavailable-source evidence is excluded from downstream use.
An attachment never changes evidence strength by itself.

Attachment admission accepts PDF and DOCX only. Presign binds a randomized private
key to one short-lived `PUT`, exact media type, and exact byte length. Finalize is
idempotent, repeats owner/object/signature admission, and creates a durable scan/
extract job. Download is available only for the same owner and a clean active
attachment through an operation-specific short-lived signed `GET`; permanent
credentials and object keys are never response fields. Evidence detail exposes
`uploading`, `scanning`, `ready`, `failed`, or `deleting` status for polling.

Achievement drafts preserve unanswered neutral prompts. `/confirm` is named for
wire compatibility but performs explicit, idempotent conversion of a reviewed
draft into one Confirmed evidence item; it does not independently verify a claim.

### Phase 4 — Roles and readiness

```text
GET    /api/v1/roles
GET    /api/v1/roles/{roleId}
GET    /api/v1/saved-roles
POST   /api/v1/saved-roles
PATCH  /api/v1/saved-roles/{savedRoleId}
DELETE /api/v1/saved-roles/{savedRoleId}
GET    /api/v1/role-readiness
POST   /api/v1/role-readiness
GET    /api/v1/role-readiness/compare
GET    /api/v1/role-readiness/{analysisId}
```

All Phase 4 routes require an authenticated account session. Mutations also
require session CSRF/origin controls. Saved-role update/delete requires strict
quoted positive-int32 `If-Match`; analysis requires `Idempotency-Key`.
`GET /api/v1/role-readiness/compare` accepts two or three `roleId` query values.
Readiness responses include engine/configuration/feature-schema versions, the
versioned role taxonomy, raw and display scores, component contributions,
competency states, evidence links by title/state, history, and the canonical
internal-score disclaimer. The service consumes an owner-scoped Career Record
readiness snapshot and returns `404` for cross-user saved roles or analyses.

### Phase 5 — Jobs, matching, and opportunity priority

```text
POST   /api/v1/jobs/import
POST   /api/v1/jobs
GET    /api/v1/jobs
GET    /api/v1/jobs/{jobId}
PATCH  /api/v1/jobs/{jobId}
DELETE /api/v1/jobs/{jobId}
POST   /api/v1/jobs/{jobId}/analyze
GET    /api/v1/job-match-analyses/{analysisId}
GET    /api/v1/job-match-analyses/{analysisId}/requirements
POST   /api/v1/jobs/{jobId}/opportunity-priority
GET    /api/v1/opportunity-priorities/{priorityId}
```

All endpoints require an authenticated user. Mutations require CSRF. Create,
URL import, analysis, and opportunity priority require `Idempotency-Key`; update
and delete require `If-Match` with the current job version. Responses are
owner-scoped and never authorize access by ID alone.

URL import accepts HTTP(S) only, rejects credentials and non-public resolved
addresses, validates every redirect, caps response size/redirects/time, accepts
plain text or HTML, strips script/style/template content, and stores only plain
text. Extracted requirements include source spans and confidence. Match analyses
store immutable requirement match rows and evidence-link snapshots so later job
edits do not rewrite historical results. Readiness and priority responses include
the canonical internal-score disclaimer.

### Phase 6 — Change Studio and grounded AI

```text
POST   /api/v1/change-sets
GET    /api/v1/change-sets/{changeSetId}
POST   /api/v1/change-sets/{changeSetId}/operations/{operationId}/accept
POST   /api/v1/change-sets/{changeSetId}/operations/{operationId}/reject
POST   /api/v1/change-sets/{changeSetId}/operations/{operationId}/edit
POST   /api/v1/change-sets/{changeSetId}/operations/{operationId}/alternatives
POST   /api/v1/change-sets/{changeSetId}/operations/{operationId}/lock
POST   /api/v1/change-sets/{changeSetId}/operations/{operationId}/unlock
POST   /api/v1/change-sets/{changeSetId}/apply-safe
POST   /api/v1/change-sets/{changeSetId}/undo
POST   /api/v1/change-sets/{changeSetId}/redo
POST   /api/v1/change-sets/{changeSetId}/versions/{versionId}/restore
POST   /api/v1/clarifications/{clarificationId}/answer
```

All routes require an authenticated account session. Mutations require CSRF,
`Idempotency-Key`, and the current quoted positive-int32 `If-Match` version,
except creation, which requires CSRF and idempotency and returns the initial ETag.
Structured operations, claim ledgers, provider metadata, grounding results, and
clarifying questions are server-calculated; clients cannot waive confirmation,
mark output as grounded, or attach arbitrary evidence/requirement IDs. Responses
are `no-store`, owner-scoped, and include the canonical internal-score
disclaimer wherever expected score movement appears.

### Phase 7 — Resumes and verified export

```text
GET    /api/v1/resumes
POST   /api/v1/resumes
GET    /api/v1/resumes/{resumeId}
GET    /api/v1/resumes/{resumeId}/source-options
PATCH  /api/v1/resumes/{resumeId}
GET    /api/v1/resumes/{resumeId}/versions
POST   /api/v1/resumes/{resumeId}/versions
GET    /api/v1/resume-versions/{versionId}
POST   /api/v1/resumes/{resumeId}/restore/{versionId}
POST   /api/v1/resume-versions/{versionId}/export
GET    /api/v1/exports/{exportId}
GET    /api/v1/exports/{exportId}/verification
POST   /api/v1/exports/{exportId}/download-intent
DELETE /api/v1/exports/{exportId}
```

All routes require an authenticated account session. Mutations require CSRF.
Resume creation, immutable version creation, version restore, export, download
intent creation, and export deletion require `Idempotency-Key`; mutable resume
updates, version creation from the current draft, and restore require the current
quoted positive-int32 `If-Match` version. Resume reads return ETags and all
responses are `no-store`.

The service builds default drafts and editor source options from eligible
owner-scoped Career Record evidence and optional Change Studio current-version
output. Every persisted bullet carries server-rehydrated exact evidence
revision references; clients cannot supply grounding authority. Mutable updates
accept selected confirmed personal facts, section/bullet structure, linked
entities, one of five templates, and bounded page/font/spacing/margin layout.

Export returns `202 Accepted` with `pending` durable state. The response pins an
immutable version, `versionContentSha256`, and `fidelityManifestSha256`; clients
poll `GET /api/v1/exports/{exportId}` through `rendering`/`retry_wait` to
`verified`, `blocked`, or `dead_lettered`. Only `verified` can create a
short-lived ownership-checked download intent. The worker independently checks
exact occurrences, omissions/duplicates, reading order, searchability,
one/two-page limit, factual/numeric grounding, and all version/manifest pins.

Delete also returns `202 Accepted`, transitioning through
`deletion_pending`, `deleting`, and optional `deletion_retry_wait` before
`deleted`. A terminal cleanup outage is explicit as
`deletion_dead_lettered`; `deletedAt` is never populated before private object
storage confirms deletion. Both render and delete use operation-typed
transactional outbox rows, fenced leases, bounded retry, reconciliation, and
redacted audit events.

### Phase 8 — Applications and application packs

```text
GET    /api/v1/applications
POST   /api/v1/applications
GET    /api/v1/applications/calendar
GET    /api/v1/applications/{applicationId}
PATCH  /api/v1/applications/{applicationId}
PATCH  /api/v1/applications/{applicationId}/stage
DELETE /api/v1/applications/{applicationId}
GET    /api/v1/applications/{applicationId}/events
POST   /api/v1/applications/{applicationId}/events
GET    /api/v1/applications/{applicationId}/tasks
POST   /api/v1/applications/{applicationId}/tasks
PATCH  /api/v1/applications/{applicationId}/tasks/{taskId}
GET    /api/v1/applications/{applicationId}/notes
POST   /api/v1/applications/{applicationId}/notes
POST   /api/v1/applications/{applicationId}/application-packs
GET    /api/v1/applications/{applicationId}/application-packs
GET    /api/v1/application-packs/{packId}
GET    /api/v1/application-packs/{packId}/consistency
DELETE /api/v1/applications/{applicationId}/documents/{documentId}
```

Application, task, note, event, and pack creates require bounded idempotency keys
with request-fingerprint conflict detection. The web reuses one key for an
unchanged user intent and rotates it only after relevant input changes or a
successful mutation. Omitting an event time does not put a changing server clock
value in the request fingerprint; the timestamp is assigned only when the
operation executes. Mutable application and task writes use positive quoted
`If-Match` versions. Stage/outcome transitions are validated against matching
database constraints and audited, terminal-stage reopening requires a reason,
and a resume change plus its evidence snapshot, workflow event, and audit record
execute in one transaction. Nested resources are fetched by both owner and
application parent.

The server-side application snapshot pins the exact job ID/version/source
SHA-256 and typed requirement snapshot; resume ID/immutable version ID/version
number after revalidating its per-claim hash ledger; and evidence ID/revision ID/
revision number/statement SHA-256. The authorized detail response exposes the
necessary pin and claim/evidence identifiers without exposing unrelated source
content. An incomplete legacy resume/change source is refused rather than treated
as grounded. Forward migration keeps an older Change Studio claim readable with
nullable provenance fields, but downstream source adapters reject that explicitly
unpinned row; every new claim requires the complete evidence revision tuple. Pack
documents also store content hashes and exact claim-to-evidence/requirement
links. Consistency results cover source-pin drift, claims, numbers, titles, dates,
evidence, requirements, and cross-document ledger disagreement.
Deleting a document produces an audited content-free tombstone; deleting an
application requires current ownership/version and leaves redacted audit history.

Application, task, note, event, and pack-list responses use opaque cursor
pagination with bounded limits; the application detail response stays
lightweight and clients load child collections on demand. Cursor input is
validated as ASCII before strict decoding. Calendar ranges are bounded to 366
days and 500 entries. All responses are private `no-store`.
There is no autonomous submission, email/social-network delivery, contact
scraping, or message-sending endpoint in the first release.

### Phase 9 — Interview, networking, growth, and analytics

```text
GET    /api/v1/interview-prep/stories
POST   /api/v1/interview-prep/stories
GET    /api/v1/interview-prep/stories/{story_id}
PATCH  /api/v1/interview-prep/stories/{story_id}
DELETE /api/v1/interview-prep/stories/{story_id}
GET    /api/v1/interview-prep/applications/{application_id}/defense-map
GET    /api/v1/interview-prep/sessions
POST   /api/v1/interview-prep/sessions
GET    /api/v1/interview-prep/sessions/{session_id}
PATCH  /api/v1/interview-prep/sessions/{session_id}
DELETE /api/v1/interview-prep/sessions/{session_id}
GET    /api/v1/interview-prep/sessions/{session_id}/questions
POST   /api/v1/interview-prep/sessions/{session_id}/questions
POST   /api/v1/interview-prep/sessions/{session_id}/questions/generate
GET    /api/v1/interview-prep/sessions/{session_id}/notes
POST   /api/v1/interview-prep/sessions/{session_id}/notes
PATCH  /api/v1/interview-prep/sessions/{session_id}/notes/{note_id}
DELETE /api/v1/interview-prep/sessions/{session_id}/notes/{note_id}
GET    /api/v1/interview-prep/sessions/{session_id}/follow-up-drafts
POST   /api/v1/interview-prep/sessions/{session_id}/follow-up-drafts/generate

GET    /api/v1/networking/organizations
POST   /api/v1/networking/organizations
GET    /api/v1/networking/organizations/{organization_id}
PATCH  /api/v1/networking/organizations/{organization_id}
DELETE /api/v1/networking/organizations/{organization_id}
GET    /api/v1/networking/contacts
POST   /api/v1/networking/contacts
GET    /api/v1/networking/contacts/{contact_id}
PATCH  /api/v1/networking/contacts/{contact_id}
DELETE /api/v1/networking/contacts/{contact_id}
GET    /api/v1/networking/contacts/{contact_id}/consent
POST   /api/v1/networking/contacts/{contact_id}/consent/grants
POST   /api/v1/networking/contacts/{contact_id}/consent/withdrawals
GET    /api/v1/networking/contacts/{contact_id}/notes
POST   /api/v1/networking/contacts/{contact_id}/notes
GET    /api/v1/networking/contacts/{contact_id}/interactions
POST   /api/v1/networking/contacts/{contact_id}/interactions
GET    /api/v1/networking/contacts/{contact_id}/referrals
POST   /api/v1/networking/contacts/{contact_id}/referrals
PATCH  /api/v1/networking/referrals/{referral_id}
GET    /api/v1/networking/templates
POST   /api/v1/networking/templates
PATCH  /api/v1/networking/templates/{template_id}
GET    /api/v1/networking/contacts/{contact_id}/reminders
POST   /api/v1/networking/contacts/{contact_id}/reminders
PATCH  /api/v1/networking/reminders/{reminder_id}
GET    /api/v1/networking/reminders/{reminder_id}/execution

GET    /api/v1/career-growth/insights
GET    /api/v1/career-growth/goals
POST   /api/v1/career-growth/goals
GET    /api/v1/career-growth/goals/{goal_id}
PUT    /api/v1/career-growth/goals/{goal_id}
DELETE /api/v1/career-growth/goals/{goal_id}
POST   /api/v1/career-growth/goals/{goal_id}/milestones
PUT    /api/v1/career-growth/goals/{goal_id}/milestones/{milestone_id}
DELETE /api/v1/career-growth/goals/{goal_id}/milestones/{milestone_id}
GET    /api/v1/career-growth/development-items
POST   /api/v1/career-growth/development-items
GET    /api/v1/career-growth/development-items/{item_id}
PUT    /api/v1/career-growth/development-items/{item_id}
DELETE /api/v1/career-growth/development-items/{item_id}
GET    /api/v1/career-growth/reviews
POST   /api/v1/career-growth/reviews
GET    /api/v1/career-growth/reviews/{review_id}
DELETE /api/v1/career-growth/reviews/{review_id}
POST   /api/v1/career-growth/reviews/{review_id}/versions
POST   /api/v1/career-growth/reviews/{review_id}/finalizations
GET    /api/v1/career-growth/career-health/analyses
POST   /api/v1/career-growth/career-health/analyses
GET    /api/v1/career-growth/career-health/analyses/{analysis_id}
DELETE /api/v1/career-growth/career-health/analyses/{analysis_id}

POST   /api/v1/analytics/refreshes
GET    /api/v1/analytics/refreshes/{job_id}
GET    /api/v1/analytics/report
```

Interview stories pin exact authorized application claim, evidence revision,
revision number, and statement hash tuples. Defense maps are derived from the
current owner-authorized application view; unsupported strong claims stay
visibly undefended. Each story's pins are revalidated independently, so stale
support on one story cannot contaminate another story's defense result. Session
questions, private notes/reflections, and follow-up
drafts are nested by both owner and session. A generated follow-up is review-only
text: no send endpoint exists. A new generated question bank revalidates every
session evidence pin, and a new follow-up revalidates every selected claim's
pins, against live canonical Career Record eligibility plus exact current
revision identity, number, hash, strength, and numeric state. Changed,
unavailable, or ineligible evidence fails closed. An exact idempotent replay
returns the already persisted immutable result before this new-generation check.

Networking contact consent is purpose-specific and append-only. Grant and
withdrawal records are not inferred from account consent or imported application
contacts. Withdrawing collection or storage consent also withdraws every active
purpose, irreversibly tombstones the contact parent, and redacts all contact
child personal/free-text fields; content-free consent, audit, and queue state
remains where required. Consent policy versions are server-owned enum values:
clients must attest the current `networking-contact-consent/1` value, and the
database permits only that value plus the internal deletion-policy identifier,
preventing arbitrary contact content from entering the retained ledger.
Outreach-only withdrawal preserves the contact, note
bodies, and inbound/mutual history while cancelling referrals/reminders and
redacting outbound, template-linked, or referral interactions plus referral
context and reminder titles. Organization/contact deletion, consent, child
collections, templates, and local reminders are ownership-scoped and audited.
Every collection uses a bounded, ASCII-validated opaque cursor tied to its owner,
parent, and filter purpose. Owner/contact quotas bound organizations, contacts,
templates, notes, interactions, referrals, reminders, consent history, and
reminder occurrences. Reminder execution returns either `null` or only
occurrence ID/number, scheduled time, occurrence/queue status, attempt limits,
and a safe error code; it never returns a lease, contact content, message, or
destination and exposes no delivery action.
Reactivating an explicitly completed or cancelled reminder creates a fresh
occurrence and outbox row; it does not reuse terminal work or revive content
redacted by a consent withdrawal.

Career Growth uses exact eligible evidence pins for goals, milestones,
development items, and immutable review versions. The insights response derives
current eligible `achievement` evidence and skill-evidence coverage directly
from Career Record, returns the six deterministic Promotion Readiness checks and
their non-predictive disclaimer, and lists annual resume-refresh development
items; it does not persist a competing achievement/skill authority. Promotion
checks for completed milestones, completed promotion plans, finalized reviews,
and completed annual refreshes, plus the annual-refresh evidence links returned
by insights, include only stored pins whose evidence ID, revision ID/number,
statement hash, and revision timestamp still match the live eligible Career
Record snapshot.
Versioned writes require quoted `If-Match`; creates/finalizations/analyses use
stable idempotency. Finalization requires at least one evidence link and
revalidates that the exact evidence ID, revision ID/number, statement hash, and
eligibility are still current before creating the immutable final version.
Career Health v1 returns the canonical internal-score disclaimer,
formula/configuration versions, applicable-component trace, and
`insufficient_data` instead of a deceptive number when its minimum input
threshold is not met. Snapshot hashes are verified before stored analyses are
returned.

Analytics refreshes are durable owner-scoped jobs with bounded windows,
IANA timezone validation, idempotency, owner-serialized active/history quotas,
leases, retries, dead-letter state, source watermarks, and private `no-store`
polling. The timezone is part of job and snapshot identity and controls local
calendar cohorts and event buckets. Reports include versioned metric, cohort,
timestamp, and suppression definitions; exact freshness/source watermarks;
requirement-coverage trends; observed outcomes grouped by exact immutable resume
version; cohort sufficiency; and null-suppressed rates/averages below a
denominator of five. The stored payload hash is revalidated before display.
Interview/offer event buckets are calculated only from applications in the
report's selected cohort. Achievement points are restricted to current canonical
Career Record evidence whose type is exactly `achievement`. Supplemental reads
reject more than 500 Role Readiness points or 2,000 achievement points, and the
freshness token hashes the exact bounded readiness/achievement point set for the
same guarded source window used by the refresh. Eligibility or point-set drift
therefore persists a safe stale audit state and retries without presenting the
stale output as current. Every report uses the canonical non-causal
interpretation. No raw resume, evidence, contact, note, offer, rejection, or
generated-document prose enters the aggregate.
Dead-letter and expired-lease reconciliation terminalize the associated job in
the same transaction, so a terminal outbox cannot strand its job in `queued`.

All four Phase 9 route families advertise the shared safe `413` body-limit
problem and a typed `429` quota problem. Domain collection limits raise the
family-specific quota code; they are not reported as a generic validation or
conflict failure.

### Phase 10 planned API — Privacy operations and connected services

The endpoints in this subsection are design targets only. They are not
implemented or present in the current OpenAPI contract. Profile, locale,
timezone, writing/search preferences, sessions, consent, password changes,
redacted security activity, Google connection state/removal, and Career Record
reminder preferences already use the implemented Phase 1/3 APIs above.

```text
POST   /api/v1/data-exports
GET    /api/v1/data-exports/{exportId}
POST   /api/v1/account-deletion
GET    /api/v1/account-deletion/{requestId}
POST   /api/v1/account-deletion/{requestId}/cancel
GET    /api/v1/connected-services
DELETE /api/v1/connected-services/{connectionId}
```

When implemented, sensitive actions will require recent authentication and
idempotency. Data export/deletion will be tracked async operations covering
relational, object, vector, cache, provider, and documented backup-lifecycle
behavior.

### Phase 10 planned API — Billing and administration

The endpoints in this subsection are design targets only. They are not
implemented or present in the current OpenAPI contract.

```text
GET    /api/v1/plans
GET    /api/v1/subscription
POST   /api/v1/subscription/checkout
POST   /api/v1/subscription/portal
POST   /api/v1/webhooks/billing/{provider}
GET    /api/v1/admin/system-health
GET    /api/v1/admin/processing-jobs
POST   /api/v1/admin/processing-jobs/{jobId}/retry
GET    /api/v1/admin/audit-events
GET    /api/v1/admin/feature-flags
PATCH  /api/v1/admin/feature-flags/{flagId}
GET    /api/v1/admin/role-taxonomy
PATCH  /api/v1/admin/role-taxonomy/{roleId}
GET    /api/v1/admin/templates
PATCH  /api/v1/admin/templates/{templateId}
```

When implemented, webhook endpoints will authenticate the raw provider payload
and use provider event ID plus request hash for idempotency. Admin retry will be
allowed only for classified safe states and will not bypass tenant ownership or
duplicate side effects.

## Score response requirements

Every score response includes:

- score type, immutable analysis/input snapshot, engine and configuration version;
- raw fixed precision or basis points and separately rounded display value;
- components, weights, feature contributions, evidence/source references the
  current user is authorized to see, and explanations;
- hard gaps, warnings, missing/unknown/not-applicable treatment, and timestamp;
- the canonical internal-score disclaimer or a stable localization key plus
  complete rendered text.

The API never labels the value an employer score, hiring probability, or guarantee.
See `docs/scoring-methodology.md`.

## Grounded generation response requirements

Generated responses carry typed operations, before/after, atomic claim ledger,
eligible evidence IDs, requirement IDs, reason, confidence/risk, grounding result,
confirmation state, provider/prompt/policy versions, and deterministic expected
score effect when available. Evidence is independently loaded and authorized by
the server.

An unsupported operation is not returned as accept-able content. The API returns
a safe blocked finding or clarifying question. User-edited text is revalidated
before a new immutable version is created. See `docs/ai-grounding-policy.md`.

## Rate, size, and abuse limits

Every endpoint has an explicit body/query limit and rate class. High-cost routes
also apply user/tenant/plan quota, concurrency, input pages/characters, provider
token/output, and daily cost limits. Authentication, guest upload, URL import, AI,
render, export, and deletion have specialized abuse policy. `429` includes a safe
retry time when available; clients do not spin on it.

Limits are centrally configured with secure maximums. Entitlements may lower or
raise a user's allowed use within those maximums but cannot disable security,
grounding, authorization, or content limits.

The API enforces a 1 MiB default JSON request-body maximum before route parsing.
Both declared `Content-Length` and cumulative streamed/chunked body bytes are
bounded and return a safe `413` problem when exceeded. Resume bytes do not pass
through that JSON boundary: an upload intent enforces the exact byte count and
the API rechecks object metadata and signature at finalization. The account and
guest upload-intent routes also apply the configured Redis-backed rate class;
the backend separately enforces one active guest intake and at most 25 active
registered-account intakes. Canonical correction and analysis use independent
ownership-scoped Redis rate classes (defaults: 30 corrections per minute and 10
analyses per hour). The domain also caps a document at 50 canonical revisions and
100 analysis jobs, returns the completed result for an already analyzed immutable
snapshot, rejects concurrent work, and rejects a correction whose requested
values make no actual change.

## OpenAPI and generated contracts

- FastAPI operation IDs are stable and unique.
- Schemas distinguish create/update/read, secret write-only fields, immutable
  server fields, and discriminated unions for jobs/operations/evidence.
- Examples are synthetic and contain no real private data.
- CI exports a normalized OpenAPI file and detects unexplained drift for Phase 0
  and every later route. The TypeScript package is generated from that artifact
  using a pinned generator.
- Generated schema code is not manually patched. Contract changes update API
  schemas, compatibility notes, the typed client wrapper, tests, and this document
  together.
- Security schemes, error responses, idempotency, rate responses, and ownership
  expectations are documented per operation.

## API versioning and deprecation

Additive optional response fields are allowed within v1 when clients ignore
unknown fields. Removing/renaming fields, changing meaning/type, narrowing accepted
input incompatibly, or altering state/idempotency semantics requires a versioned
migration or a documented deprecation window.

Deprecation includes response metadata/documentation, owner and removal date,
usage monitoring without sensitive payloads, and client migration. Historical
resume, evidence, model, and score schema versions remain readable even after the
write API advances.

## API verification

Foundation probes:

```sh
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ready
curl --fail http://localhost:8000/api/v1/meta
curl --fail http://localhost:8000/openapi.json
```

Phase 1's consolidated local gate is:

```powershell
.\scripts\verify-phase1.ps1
```

Phase 2's consolidated gate is implemented as:

```powershell
.\scripts\verify-phase2.ps1
```

It includes generated-contract drift, migration `20260715_0003` round trip,
real PostgreSQL/Redis/MinIO/ClamAV integration, restricted worker runtime, and the
registered and guest Resume Health browser journeys. Local gates and hosted run
`29378312134` pass as recorded in `PLANS.md`.

Phase 3's blocking consolidated gate is:

```powershell
.\scripts\verify-phase3.ps1
```

It retains every Phase 2 gate and adds migration `20260715_0004`, Career Record
repository and real S3/ClamAV attachment-provider integration, durable attachment
worker/reconciliation checks, generated-contract drift, and the authenticated
desktop Career Profile/Evidence/Achievement journey. The journey is intentionally
run once on desktop; shared workspace mobile behavior is covered by existing
responsive suites. The final local consolidated result passes; hosted Phase 3 CI
evidence also passes as recorded in `PLANS.md`.

Tests assert exact safe response schemas and problems, correlation IDs, readiness
failure under dependency loss, no secret leakage, stable operation IDs, OpenAPI
and generated-schema freshness, unauthenticated and cross-user denial, refresh
rotation/replay, one-use recovery, CSRF/origin policy, OAuth state/link collision,
abuse limits, audit events, optimistic profile/onboarding updates, and the 1 MiB
streaming body limit. Real PostgreSQL/Redis integrations and the browser auth
journey run in isolated Compose projects. Exact results are recorded in
`PLANS.md`.

Phase 2 adds API/backend assertions for configured upload policy, account and
guest scope, capability-cookie behavior, CSRF/origin and upload rate policy,
immutable correction/version conflicts, job/idempotency state, and score
version/hash/disclaimer output. Real storage/scanner/repository contracts and
registered/guest browser workflows run through the isolated Phase 2 project. The
local result is API 67 and contracts 3 with clean generated-contract drift; full
counts and hosted evidence are recorded in `PLANS.md`.

Phase 3 adds API/backend assertions for authenticated CSRF and owner scope,
partial-date and unknown-field validation, strict preconditions, proposal-only
resume import, source deletion/availability, evidence transitions and numeric
eligibility, conflict resolution, idempotent achievement conversion, private
attachment admission/access/deletion, lost-worker reconciliation, safe problem
mapping, and production service composition. Exact final counts belong in
`PLANS.md`; the local consolidated gate passed on 2026-07-19.

Phase 4's consolidated gate is:

```powershell
.\scripts\verify-phase4.ps1
```

It retains every Phase 3 gate and adds migration `20260719_0005`, Role Explorer
repository integration, generated-contract drift, API tests for authentication,
CSRF, owner scope, idempotency, version preconditions and comparison, and the
authenticated desktop Role Explorer save/analyze/compare journey.
The local consolidated gate passed on 2026-07-19; exact evidence is recorded in
`PLANS.md`.

Phase 5 through Phase 7 retain those API gates while adding Job Match, Change
Studio, and Resume Builder routes and their migration, contract, ownership,
grounding, idempotency, concurrency, renderer, and browser checks. Their
consolidated local results are recorded in `PLANS.md`.

Phase 8's consolidated gate is:

```powershell
.\scripts\verify-phase8.ps1
```

It retains the prior gates and adds migration `20260724_0009`, generated-contract
drift, Application Workspace repository/source integration, exact historical
revision/hash provenance, legacy-source refusal, owner/nested-parent denial,
opaque pagination, stable idempotency, `If-Match` conflicts, consistency and
deletion behavior, and complete desktop/mobile application workflows.
`scripts/verify-phase8.ps1` exited 0 in 273 seconds on 2026-07-24 for
implementation revision `964cd9c`: the API portfolio reported `104 passed`, the
backend portfolio `206 passed`, the web portfolio `121 passed` across 35 files,
and the production build emitted 39 routes. Migration head
`20260724_0009`, downgrade to `20260719_0008`, forward repair, integrations,
worker/runtime/container probes, and the configured browser portfolio all
passed. Playwright discovered 16 tests and completed with 10 passed and 6
intentional inherited mobile skips; Application Workspace passed its full
desktop and mobile journeys.

The separate security scan also passed with no known dependency-audit
vulnerabilities, no fixable-high API/worker findings, and no web or `web-edge`
vulnerabilities. The three remaining medium Python-runtime findings have fixes
only in Python 3.15 prereleases and are nonblocking under policy. PR #21 workflow
runs `30126993025` and `30128304892` passed every required hosted job.

Phase 9's consolidated gate is:

```powershell
.\scripts\verify-phase9.ps1
```

It retains every predecessor gate and adds migration `20260724_0010`, rollback to
`20260724_0009`, canonical and pre-release-drift forward repair, the four Phase 9
repository/API portfolios, durable analytics and local-reminder workers,
generated-contract drift, and the authenticated desktop/mobile Phase 9 career
workspace journey. The final local tree passed with 365 backend, 134 API, 84
worker, and 150 web tests across 43 files; the production build emitted 48
routes. PostgreSQL integration passed 39 tests with 7 inherited SQLAlchemy cycle
warnings, and Playwright completed 12 tests with 6 intentional inherited mobile
skips while the Phase 9 desktop/mobile journeys both passed. The separate
security scan also passed. PR #22 workflow run `30161489265` passed every
required hosted job at implementation/merge head `1454792`. Exact authoritative
evidence and residual findings are recorded in `PLANS.md`.
