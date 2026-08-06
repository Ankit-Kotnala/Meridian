# ADR 0015: Phase 9 Interview, Networking, Growth, and Analytics Boundaries

Status: Accepted
Date: 2026-07-24

## Context

Phase 9 adds four workflows with materially different data and trust boundaries:
interview preparation grounded in application claims, a private relationship
workspace, longitudinal career planning, and aggregate outcome analytics.
Combining them in one generic module would allow private notes or contact data to
leak into generation or analytics and would blur consent, provenance, scoring,
and retention rules.

The Career Record and its evidence graph remain the factual authority.
Application Workspace owns the immutable job, resume-version, claim, requirement,
and evidence pins used for a specific application. Rezumi must not scrape
contacts, send outreach, invent an interview answer, turn a planned credential
into an achievement, or describe observed outcomes as causal or predictive.

## Decision

Add four Phase 9 bounded contexts under `rezumi.modules`:
`interview_prep`, `networking`, `career_growth`, and `career_analytics`. Each owns
its persistence, application service, ports, idempotency records, and redacted
audit events. Cross-context reads use purpose-minimized application interfaces;
one context never queries another context's tables.

### Interview preparation

- Build the Resume Defense Map from Application Workspace's exact immutable
  claim, requirement, resume-version, and evidence-revision/hash pins. A
  deterministic rule classifies claims as defended, partially defended, or
  undefended and warns when a strong claim lacks a ready story. Matching ready
  stories are live-revalidated at read time; rejected pins remain immutable
  history but are shown as partial and needing review, never defended.
- Store STAR stories as structured situation, task, action, result, personal
  contribution, metric explanation, and confidence fields. Ready or generated
  factual statements retain machine-checkable claim/evidence provenance.
  Every create or edit resulting in `ready` revalidates all selected exact pins
  against current canonical eligibility before persistence. Unsupported numbers
  are refused and missing facts produce questions or warnings, never plausible
  filler; an exact create replay remains immutable.
- Snapshot only the bounded role, requirement, claim, and evidence context needed
  for an interview session. Private application notes, contacts, offers,
  rejection explanations, and application-pack prose are excluded.
- Questions, answer notes, reflections, and follow-up drafts remain private.
  Follow-up output is a user-reviewed grounded draft. No email, calendar,
  applicant-tracking, or social-network delivery capability is added.
- Before creating a new generated question bank or follow-up draft, revalidate
  every relevant immutable session evidence pin through Application Workspace
  against live canonical Career Record eligibility and the exact current
  revision tuple. An exact idempotent replay remains the same historical
  immutable artifact rather than being silently regenerated.

### Networking

- Use a dedicated third-party contact consent ledger. Phase 1 consent records
  describe the account holder's product choices and are not evidence that a
  contact consented to collection, storage, or outreach.
- Contact creation requires an explicit user attestation for collection and
  storage. Outreach-related drafts, referrals, interactions, and reminders
  require current outreach consent. Withdrawal immediately blocks new
  outreach-related artifacts and cancels pending reminders.
- Consent policy identifiers are server-owned, versioned constants rather than
  user-authored text. The HTTP contract accepts only the current attestation
  identifier, and the database allowlists current/deletion identifiers so the
  retained ledger cannot be used to preserve contact PII.
- Organizations, contacts, tags, private notes, interactions, referrals,
  templates, reminders, and reminder occurrences remain owner-scoped. Contact
  deletion redacts personal content and preserves only the minimum content-free
  audit record justified by security and idempotency.
- Reminders are local workspace state. The durable reminder worker may
  idempotently materialize due occurrences, recover leases, and dead-letter safe
  failures, but it does not email, message, push, scrape, or fetch contact URLs.
- Withdrawal of collection or storage is destructive: withdraw every active
  purpose, tombstone all contact-parent PII, and redact all contact-child
  personal/free-text content while retaining only required content-free consent,
  audit, and queue state. Outreach-only withdrawal retains the contact, notes,
  and inbound or mutual history, but cancels pending work and redacts outbound,
  template-linked, and referral/reminder content.
- Do not backfill Phase 8 application contacts into Networking because no
  equivalent contact-consent evidence exists.

### Career growth and Career Health

- Career Growth stores goals, milestones, development plans, promotion/internal
  mobility preparation, learning/certification tracking, and versioned
  quarterly/annual reviews. Achievements and evidence remain Career Record data
  and are referenced only by exact authorized evidence-revision/hash pins.
- A planned certification or skill is not presented as achieved. A completed
  credential or factual review statement requires eligible evidence; a missing
  source creates an explicit question or incomplete state.
- Finalized review versions are immutable. A material edit creates a new version
  with its reason, source snapshot, and accept/reject/edit history rather than
  silently rewriting published history.
- Career Health v1 is deterministic integer-basis-point arithmetic with these
  weights: evidence currency 2500, goal progress 3000, development follow-through
  2000, review cadence 1500, and readiness maintenance 1000. A numeric score is
  emitted only when at least three components and 6000 basis points of weight are
  applicable; otherwise the result is `insufficient_data`.
- Persist the immutable input snapshot and hash, engine/configuration versions,
  component values, contributions, missing/not-applicable reasons, findings, and
  calculation time. Career Health is a longitudinal maintenance measure, not job
  market value, an employer or ATS score, a hiring probability, or a guarantee.

### Career analytics

- Analytics consumes complete, keyset-paginated owner-scoped source views plus
  source watermarks. The Phase 8 fixed first-1000-record view is replaced; silent
  truncation is prohibited.
- Aggregation runs as an idempotent durable job with a bounded window, lease and
  fencing token, retry/dead-letter behavior, trace ID, pre/post watermark check,
  and immutable snapshot. A changed watermark makes the result stale and causes
  a retry; stale output is never presented as current.
- Allowed inputs are bounded workflow metadata such as timestamps, stage/outcome,
  role family/title, industry, source, pinned resume version, requirement
  category, score/configuration version, and safe counts. Notes, contact
  identity, message/template text, offer or rejection text, raw resumes, evidence
  statements, attachments, job-description prose, application-pack content, and
  model output are excluded.
- Counts may be shown. Rates and percentages are suppressed with a `null` value
  when their denominator is below five. Time series use at most 24 buckets and
  dimension breakdowns at most 20 values plus `other`.
- Every response includes its metric definition and version, bounded window,
  source watermark/freshness, cohort sufficiency, and correlation-only
  interpretation. Product and test copy must not claim causation, prediction,
  hiring probability, or improved chances.
- Achievement growth consumes only current canonical-eligible Career Record
  evidence whose type is exactly `achievement`. Time-bucketed application events
  remain inside the application cohort selected for the report. Role Readiness
  history and achievement history are hard-bounded, and the supplemental
  freshness token hashes the exact bounded point set for the same guarded source
  window used by aggregation.

### Shared delivery rules

- Phase 9 persistence is introduced by one additive migration after
  `20260724_0009`. Every user-owned row carries explicit ownership; child
  constraints include owner plus parent; domain enums and database checks must
  remain executable parity.
- Migration `20260724_0010` may conditionally repair the three canonical nullable
  Change Studio provenance columns, their all-null/all-complete check, and stale
  Application Workspace resume-change event/audit enum checks when a pre-release
  development database was stamped by an earlier Phase 8 migration copy. The
  shipped `20260724_0009` file remains immutable, a canonical Phase 8 database is
  a no-op, and downgrade leaves Phase 8-owned objects intact.
- Reads require an authenticated owner-scoped session and return private
  `no-store` responses. Mutations require CSRF. Retriable creates/analyses use a
  bounded idempotency key and request fingerprint; mutable/deletion operations
  use optimistic concurrency.
- API payloads are strict and bounded, list reads use opaque ASCII-safe cursor
  pagination, and cross-owner access returns the same not-found result as a
  missing resource.
- The web exposes complete loading, empty, success, failure, retry, conflict, and
  insufficient/suppressed states. Charts have equivalent semantic tables and
  text summaries; all workflows have keyboard and non-drag mobile paths.

## Implementation clarification (2026-07-25)

This clarification records the concrete implementation of the accepted
boundaries without changing their authority:

- Career Growth's achievement history includes only current eligible Career
  Record evidence whose type is `achievement`. Its skill dashboard may reference
  any currently eligible evidence linked to a documented skill. Both are live,
  owner-authorized derived reads; Phase 9 does not persist a competing
  achievement or skill source of truth.
- Promotion Readiness is a six-check preparation report over eligible
  achievements, skill evidence, completed evidenced milestones, an evidenced
  promotion plan, an evidence-backed finalized review, and an evidenced annual
  resume refresh. Its `insufficient_evidence`, `building`, and `review_ready`
  states are not a score, employer decision, promotion probability, guarantee,
  or assessment of job-market value.
- Annual resume refresh is a tracked development workflow. Marking it complete
  requires eligible evidence, but the workflow never silently creates, rewrites,
  publishes, or exports a resume.
- Career review finalization is idempotent and requires at least one exact
  evidence link. Eligibility, evidence/revision IDs, revision number, and
  statement SHA-256 are revalidated immediately before the immutable finalized
  successor is created. A delayed retry returns that exact finalized version and
  its then-current history even when a later draft exists.
- Exact historical replay is limited to the explicitly immutable STAR-story
  create response, generated question/follow-up artifacts, and career-review
  finalization. Other mutable creates preserve stable resource identity and
  return the current owner-authorized representation; deletion or consent
  redaction never restores historical sensitive content.
- Promotion checks for completed milestones, completed promotion plans,
  finalized reviews, and completed annual refreshes, plus annual-refresh links
  returned by insights, count or expose a stored pin only while its exact revision
  ID/number/hash/timestamp matches live eligible evidence. The database
  provenance trigger executes on every evidence-link insert or update, including
  mutations to non-key fields.
- Networking collection/storage withdrawal and contact deletion irreversibly
  tombstone the contact and redact all child personal/free-text content.
  Outreach-only withdrawal retains notes and inbound/mutual history while
  redacting outbound, template-linked, and referral/reminder material. Later
  terminal-state updates cannot restore the redacted content. Every pagination
  cursor is bound to owner, collection, parent, normalized filters, and sort
  semantics.
- Networking owner/contact quotas bound every CRM collection. Local reminder
  occurrence/outbox rows propagate one validated trace ID through worker audit
  and log context. Safe retention prunes only acknowledged/cancelled occurrences
  paired with processed/cancelled outbox rows; pending, leased, retryable, and
  dead-letter history is retained, and recurrence stops at the hard cap.
- Analytics uses IANA timezones for application cohorts and event buckets, and
  the timezone is part of refresh/snapshot identity. Versioned definitions state
  every metric's cohort, numerator/denominator, event timestamp, and suppression
  policy. Requirement-coverage trends and outcome rates by exact immutable resume
  version use the same five-record suppression floor as other rates/averages.
- Phase 9 serializes quota/idempotency decisions with transaction-scoped owner or
  parent locks. Database validation enforces exact Growth owner/evidence/revision
  ID/number/timestamp/hash provenance, immediate same-review predecessor chains,
  latest review version tuples, and Networking reminder occurrence ownership.
- Career Health and Analytics snapshot hashes are verified before display.
  Analytics report reads persist safe stale audit state without enqueueing work;
  a refresh whose before/after source watermarks change schedules its own bounded,
  durable retry. The supplemental watermark is window-aware and
  derived from the exact canonical-eligible achievement and bounded Role
  Readiness point set, so an eligibility-only change also invalidates freshness;
  neither tampered nor stale payloads are returned as current.
- Analytics keeps the public 3,650-day delta while allowing only the two
  additional UTC guard days at its internal Career Record and Role Readiness
  source boundaries. Provider limits and unavailability are translated into
  Analytics-owned safe states. API and worker aggregation share the same owned
  Resume Health and clean-attachment eligibility adapters, and worker logs bind
  the persisted refresh trace.
- Growth evidence-link target validation acquires a key-share lock on the exact
  owned goal, milestone, development item, or review version, preventing a
  concurrent target delete from committing an orphaned polymorphic link.
- Phase 9 domain collection limits use typed quota errors mapped to safe `429`
  problems. Each Phase 9 route family declares the shared streamed-body `413`
  response.

## Consequences

Four modules and their explicit source adapters create more files than a shared
CRUD service, but keep consent, provenance, scoring, and analytics exclusions
independently testable. Exact pins and immutable snapshots duplicate a bounded
amount of metadata while preventing later source edits from changing history.

The first question/follow-up generators may be deterministic. A later model
provider may improve wording only behind the existing structured grounding,
schema, timeout, cost, retry, and user-review controls.

No Phase 9 connector sends messages or reminders externally. Adding delivery,
contact import, calendar synchronization, organization membership, or provider
analytics is a new sensitive-data flow requiring a later ADR, consent design,
threat review, and rollback plan.
