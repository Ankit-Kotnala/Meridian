# ADR 0017: Observed Onboarding and Semantic Career Imports

Status: Accepted
Date: 2026-07-26

## Context

The Phase 1 onboarding record currently stores only browser-supplied Resume
Health handoff flags. It cannot distinguish an upload that is processing, a
failed document, a typed resume awaiting review, a reviewed semantic snapshot,
or a completed analysis. The browser can therefore advance the displayed flow
without the server having observed the corresponding Resume Health state.

The Phase 3 resume-import endpoint also accepts a client-authored career entity
plus one generic block span. That legacy shape cannot prove which reviewed
semantic field supplied each proposed value, cannot represent contact or skill
proposals without inventing parallel authorities, and does not use the typed
sidecar introduced by ADR 0016.

## Decision

### Server-observed onboarding

- Identity owns persisted onboarding intent, explicit skips, preferences,
  completion, and optimistic concurrency.
- Resume Health exposes an owner-scoped application query adapter that reports
  the latest document's safe lifecycle state, typed review state, and analysis
  availability. Identity never reads Resume Health tables.
- Upload, processing, review-required, reviewed, analysis-ready, and failed
  statuses are read-only observations. Onboarding update requests cannot submit
  them.
- The application service validates attempted step advancement against either an
  observed prerequisite or an explicit saved skip. A resource UUID is never
  treated as authorization.

### Typed Career Record proposals

- A server-side Career Record use case reads one owner-scoped reviewed
  `CanonicalSemantics` snapshot through an explicit Resume Health query.
- Only `confirmed`, `corrected`, and explicit `user_added` semantic fields are
  proposal input. `unreviewed` and `removed` values are excluded.
- Contact values become personal/contact fact proposals, skills become skill
  proposals, and experience, education, project, and certification values become
  typed entity proposals. These candidates do not overwrite durable Career
  Record state.
- Every parser-derived proposed field retains its semantic entity/field ID and
  exact source anchors. User-added fields retain their explicit unanchored
  origin. Acceptance is optimistic, audited, and records the reviewed values and
  provenance used to create or update the canonical record.
- Existing generic whole-block proposals remain readable for historical audit,
  but new UI and downstream flows use typed semantic proposals.

### Confirmation and downstream eligibility

- Personal/contact facts and canonical career entities expose explicit
  confirmation state. Per-field provenance is stored independently of mutable
  display projections.
- New manual records require an explicit owner confirmation action. Accepted
  import candidates are owner-confirmed by that decision; editing a proposal
  records the edit without claiming the resume contained the new wording.
- Downstream factual snapshots include only currently confirmed canonical values
  and otherwise return an explicit gap. Historical records are retained and are
  never silently upgraded to confirmed.

### Account-security Settings boundary

- Identity exposes one read-only Settings capability query. It combines
  persisted account security state with server configuration and returns only
  capabilities whose workflows actually exist.
- Password change requires a recent authenticated session, verifies the current
  password when one exists, invalidates reset tokens, and revokes every session
  on success. A recently authenticated OAuth-only account may set its first
  password.
- Security activity is a bounded redacted owner view of audit events. Google
  disconnection is allowed only when another login method remains.
- Export, deletion, billing, and scheduled notification delivery stay disabled
  until their complete provider/workflow boundaries exist. The web renders that
  server decision and does not infer capability from a button or environment
  string.

## Consequences

- The identity API gains read-only pipeline observations while its mutation
  payload becomes smaller and less forgeable.
- Career Record persistence gains additive confirmation, personal-fact,
  relationship, and field-provenance structures. Existing immutable evidence and
  legacy proposal history remain intact.
- OpenAPI and generated TypeScript contracts change in the same revision.
- Settings may explain unavailable billing, connection, export, or deletion
  actions only from server configuration; the UI cannot simulate enabled
  capability.
- Sensitive account mutations keep authorization and recent-auth enforcement at
  the API/application boundary, and successful password rotation deliberately
  requires the browser to sign in again.

## Verification

- Identity service, API, and browser tests cover every observed pipeline state,
  forbidden advancement, saved skips, optimistic conflicts, and cross-owner
  isolation.
- Career Record domain, repository, API, and browser tests cover typed mapping,
  per-field anchors, user-added origin, rejection of unreviewed fields,
  accept/reject/edit concurrency, relationships, downstream filtering, and
  cross-owner denial for every new resource.
- Migration tests upgrade from the prior head, downgrade, and re-upgrade without
  converting historical data into user-confirmed facts.
- Identity service, API, PostgreSQL, and Settings UI tests cover current-password
  rejection, OAuth-only password creation, all-session invalidation,
  cross-owner security-activity filtering, Google disconnect safeguards, and
  disabled capability presentation.
