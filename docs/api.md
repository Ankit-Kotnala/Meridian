# CareerOS API conventions and route plan

Status: Phase 0 foundation plus forward route contract  
Base path for product APIs: `/api/v1`  
Last reviewed: 2026-07-14

## Implementation truth

The API's generated OpenAPI document is authoritative for implemented request and
response shapes. This document defines conventions and the intended route map.
A route listed as a future phase is not implemented merely because it appears
here.

### Phase 0 endpoints

| Method | Path           | Purpose                                                                       | Dependency behavior                                        |
| ------ | -------------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------- |
| `GET`  | `/health`      | API process liveness                                                          | Does not require downstream services                       |
| `GET`  | `/ready`       | API readiness                                                                 | Fails when a required configured dependency is unavailable |
| `GET`  | `/api/v1/meta` | Safe service name/version/environment and canonical internal-score disclaimer | No secret or detailed topology                             |

The web separately exposes `GET /api/health` for its own liveness on port 3000.
It is not part of the product API contract.

Phase 0 does not implement authentication, persisted domain resources, uploads,
scores, AI, or application workflows. `/docs` and `/openapi.json` are development
documentation endpoints and may be restricted or disabled in production.

`packages/contracts` derives its public types and client from the implemented
FastAPI OpenAPI document. The normalized artifact under
`packages/contracts/openapi` and generated files under
`packages/contracts/src/generated` are committed review artifacts; neither is an
independent contract authority. Problem, pagination, and product schemas are not
published until corresponding Pydantic models and operations exist. The current
architecture-alignment change passes both export and generation drift checks
locally; hosted CI must repeat those checks on the committed revision before
Phase 0 closes.

## Protocol and representation

- Production uses HTTPS only; JSON is UTF-8 unless an explicitly documented file
  response says otherwise.
- Product clients call `/api/v1`. Health probes remain unversioned.
- Resource IDs are UUID strings. Timestamps are UTC RFC 3339 with offset (`Z`
  preferred). Dates without time use ISO 8601 calendar dates.
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

| Header            | Direction         | Rule                                                                                                     |
| ----------------- | ----------------- | -------------------------------------------------------------------------------------------------------- |
| `X-Request-ID`    | request/response  | Client may supply a bounded safe value; edge replaces invalid values and always returns the effective ID |
| `traceparent`     | request/internal  | Valid W3C context is propagated; invalid input starts a new trace and is never trusted for authorization |
| `X-Trace-ID`      | response/internal | Effective 32-hex trace ID returned by the Phase 0 API and bound to structured logs; diagnostic only      |
| `Idempotency-Key` | request           | Required for specified retryable side-effecting `POST` operations                                        |
| `If-Match`        | request           | Required when a resource uses optimistic concurrency; contains the last observed ETag/version            |
| `ETag`            | response          | Represents a mutable resource version, not a secret                                                      |
| `X-CSRF-Token`    | request           | Phase 1 cookie-authenticated state-changing request defense, paired with origin policy                   |
| `Retry-After`     | response          | Returned for applicable `429` or temporary `503` responses                                               |

Correlation IDs are safe opaque diagnostics. They are shown in user-facing errors
and logs but never grant access.

## Authentication and authorization (Phase 1)

The browser uses API-owned secure HTTP-only session/refresh cookies. JavaScript
does not persist bearer or refresh tokens in local storage. State-changing routes
require CSRF protection and an allowed origin. Google OAuth uses state, nonce,
PKCE, and exact redirect URIs.

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
  "type": "https://careeros.example/problems/validation-error",
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

Polling is the initial completion mechanism. Server-sent events or notifications
may be added as a separate authenticated contract after need is demonstrated.

## Upload contract (Phase 2)

The intended direct-upload sequence is:

1. `POST /api/v1/uploads/presign` with filename for display, expected size and
   media type, and purpose.
2. API authorizes quota/ownership and returns a single-use, short-lived upload
   operation for a randomized private object key. It never exposes permanent
   object credentials.
3. Client uploads the bounded object to storage with the exact allowed method and
   conditions.
4. Client starts/finalizes analysis using an opaque upload ID; the API verifies
   object size/signature/MIME and ownership before queueing quarantine/scanning.
5. Status comes from the owned document/processing job resource.

Browser filename, extension, MIME, object metadata, and upload completion are
untrusted. See `docs/security-threat-model.md`.

## Route inventory by phase

The methods below are the planned public surface. Names may be refined before
implementation through OpenAPI review; once released, compatibility rules apply.

### Phase 1 — Authentication, account, and onboarding

```text
POST   /api/v1/auth/register
POST   /api/v1/auth/verify-email
POST   /api/v1/auth/resend-verification
POST   /api/v1/auth/login
POST   /api/v1/auth/logout
POST   /api/v1/auth/logout-all
POST   /api/v1/auth/refresh
POST   /api/v1/auth/forgot-password
POST   /api/v1/auth/reset-password
GET    /api/v1/auth/sessions
DELETE /api/v1/auth/sessions/{sessionId}
GET    /api/v1/auth/google/start
GET    /api/v1/auth/google/callback
GET    /api/v1/me
PATCH  /api/v1/me
GET    /api/v1/onboarding
PATCH  /api/v1/onboarding
```

Registration/login/reset responses resist account enumeration. OAuth callback
errors return through a safe fixed application route without leaking provider
tokens. Account deletion is under settings/privacy below and requires re-auth.

### Phase 2 — Upload, documents, parsing, and Resume Health

```text
POST   /api/v1/uploads/presign
POST   /api/v1/uploads/{uploadId}/finalize
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
```

Guest equivalents use a narrow, short-lived capability and never accept a user
or tenant ID from the browser as ownership. A registered-user save operation
requires explicit consent to move data out of guest retention.

### Phase 3 — Career profile, evidence, and achievements

```text
GET    /api/v1/career-profile
PATCH  /api/v1/career-profile
GET    /api/v1/experiences
POST   /api/v1/experiences
PATCH  /api/v1/experiences/{experienceId}
DELETE /api/v1/experiences/{experienceId}
POST   /api/v1/experiences/reorder
GET    /api/v1/evidence
POST   /api/v1/evidence
GET    /api/v1/evidence/{evidenceId}
PATCH  /api/v1/evidence/{evidenceId}
DELETE /api/v1/evidence/{evidenceId}
POST   /api/v1/evidence/{evidenceId}/confirm
POST   /api/v1/evidence/{evidenceId}/archive
GET    /api/v1/evidence/{evidenceId}/usage
GET    /api/v1/achievements
POST   /api/v1/achievements
PATCH  /api/v1/achievements/{achievementId}
POST   /api/v1/achievements/{achievementId}/confirm
```

Evidence transition endpoints enforce the state machine server-side and emit an
audit event. `confirm` never trusts a client-supplied “verified” status.

### Phase 4 — Roles and readiness

```text
GET    /api/v1/roles
GET    /api/v1/roles/{roleId}
GET    /api/v1/saved-roles
POST   /api/v1/saved-roles
DELETE /api/v1/saved-roles/{savedRoleId}
POST   /api/v1/role-readiness
GET    /api/v1/role-readiness/{analysisId}
GET    /api/v1/role-readiness/{analysisId}/requirements
POST   /api/v1/role-comparisons
GET    /api/v1/role-comparisons/{comparisonId}
```

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
GET    /api/v1/opportunity-priorities/{analysisId}
```

URL import accepts an HTTP(S) URL but applies destination/redirect SSRF policy.
Extracted requirements always include original source spans and uncertainty.

### Phase 6 — Change Studio and grounded AI

```text
POST   /api/v1/change-sets
GET    /api/v1/change-sets/{changeSetId}
POST   /api/v1/change-sets/{changeSetId}/operations/{operationId}/accept
POST   /api/v1/change-sets/{changeSetId}/operations/{operationId}/reject
POST   /api/v1/change-sets/{changeSetId}/operations/{operationId}/edit
POST   /api/v1/change-sets/{changeSetId}/operations/{operationId}/alternatives
POST   /api/v1/change-sets/{changeSetId}/apply-safe
POST   /api/v1/change-sets/{changeSetId}/undo
POST   /api/v1/change-sets/{changeSetId}/redo
POST   /api/v1/clarifications/{clarificationId}/answer
```

Each write requires current version/ETag. Structured operations and grounding
results are server-calculated; clients cannot waive confirmation or attach an
arbitrary evidence ID.

### Phase 7 — Resumes and verified export

```text
GET    /api/v1/resumes
POST   /api/v1/resumes
GET    /api/v1/resumes/{resumeId}
PATCH  /api/v1/resumes/{resumeId}
GET    /api/v1/resumes/{resumeId}/versions
POST   /api/v1/resumes/{resumeId}/versions
GET    /api/v1/resume-versions/{versionId}
POST   /api/v1/resumes/{resumeId}/restore/{versionId}
POST   /api/v1/resume-versions/{versionId}/export
GET    /api/v1/exports/{exportId}
GET    /api/v1/exports/{exportId}/verification
POST   /api/v1/exports/{exportId}/download-intent
```

An export references one immutable version. Download intent is ownership-checked,
short-lived, and unavailable when a critical verification result blocks release.

### Phase 8 — Applications and application packs

```text
GET    /api/v1/applications
POST   /api/v1/applications
GET    /api/v1/applications/{applicationId}
PATCH  /api/v1/applications/{applicationId}
DELETE /api/v1/applications/{applicationId}
POST   /api/v1/applications/{applicationId}/events
GET    /api/v1/applications/{applicationId}/tasks
POST   /api/v1/applications/{applicationId}/tasks
POST   /api/v1/applications/{applicationId}/application-packs
GET    /api/v1/application-packs/{packId}
GET    /api/v1/application-packs/{packId}/consistency
```

Stage transitions are validated and audited. Documents pin exact resume/evidence/
job versions. There is no autonomous submission endpoint in the first release.

### Phase 9 — Interview, networking, growth, and analytics

```text
GET    /api/v1/star-stories
POST   /api/v1/star-stories
PATCH  /api/v1/star-stories/{storyId}
POST   /api/v1/interviews
GET    /api/v1/interviews/{interviewId}
POST   /api/v1/interviews/{interviewId}/questions
GET    /api/v1/contacts
POST   /api/v1/contacts
PATCH  /api/v1/contacts/{contactId}
DELETE /api/v1/contacts/{contactId}
POST   /api/v1/contacts/{contactId}/interactions
GET    /api/v1/career-goals
POST   /api/v1/career-goals
PATCH  /api/v1/career-goals/{goalId}
GET    /api/v1/career-reviews
POST   /api/v1/career-reviews
GET    /api/v1/analytics/overview
GET    /api/v1/analytics/applications
GET    /api/v1/analytics/readiness
```

Analytics responses include metric definition/window, cohort sufficiency where
applicable, and non-causal interpretation language.

### Phases 1–10 — Settings, privacy, and connected services

```text
GET    /api/v1/settings
PATCH  /api/v1/settings
GET    /api/v1/consents
POST   /api/v1/consents
POST   /api/v1/data-exports
GET    /api/v1/data-exports/{exportId}
POST   /api/v1/account-deletion
GET    /api/v1/account-deletion/{requestId}
POST   /api/v1/account-deletion/{requestId}/cancel
GET    /api/v1/security-activity
GET    /api/v1/connected-services
DELETE /api/v1/connected-services/{connectionId}
```

Sensitive actions require recent authentication and idempotency. Data export/
deletion are tracked async operations covering relational, object, vector, cache,
provider, and documented backup-lifecycle behavior.

### Phase 10 — Billing and administration

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

Webhook endpoints authenticate the raw provider payload and use provider event ID
plus request hash for idempotency. Admin retry is allowed only for classified
safe states and does not bypass tenant ownership or duplicate side effects.

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

Phase 0:

```sh
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ready
curl --fail http://localhost:8000/api/v1/meta
curl --fail http://localhost:8000/openapi.json
```

Tests assert exact safe response schemas, status codes, correlation IDs, readiness
failure under dependency loss, no secret leakage, stable operation IDs, OpenAPI
validity, normalized artifact freshness, and generated-schema freshness. These
checks pass together in the aligned local working tree and are recorded in
`PLANS.md`. Hosted CI evidence for the eventual commit remains pending.

Later route gates include schema/validation, unauthenticated and cross-user denial,
idempotency concurrency/replay, stale version, rate/size limits, safe errors,
audit events, and the module-specific acceptance tests in
`docs/implementation-checklist.md`.
