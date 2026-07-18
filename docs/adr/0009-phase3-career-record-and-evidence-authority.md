# ADR 0009: Phase 3 career record and evidence authority

- Status: Accepted
- Date: 2026-07-15
- Deciders: Product, Security, and Engineering
- Extends: [ADR 0002](0002-career-profile-and-evidence-as-source-of-truth.md),
  [ADR 0005](0005-ownership-scoped-tenancy-and-api-owned-sessions.md), and
  [ADR 0006](0006-asynchronous-isolated-document-processing.md)

## Context

Phase 3 turns the career profile and evidence graph from an architectural promise
into durable user data. Several decisions were deliberately open: who may assign
each evidence state, how account preferences differ from career truth, what
happens when a source resume is deleted, and whether profile, evidence, and
Achievement Inbox need separate transactional boundaries.

Getting these decisions wrong would allow a client to self-assign `Verified`,
let a parsed resume overwrite career truth, create two canonical copies of target
preferences, or silently destroy evidence when its source document is removed.
Evidence attachments also contain hostile, highly sensitive input and cannot be
treated as ordinary form fields.

## Decision

### One Phase 3 transactional bounded context

Use one backend product module named `career_record` for the career profile,
typed career entities, evidence graph, conflicts, import proposals, Achievement
Inbox, reminder preferences, and their append-only audit. These capabilities have
one consistency boundary: accepting a proposal, resolving a conflict, or
converting an achievement must atomically update the career/evidence records and
their audit history.

This is one bounded context, not one undifferentiated model. Domain types,
application commands/queries, persistence adapters, and API delivery remain
separated. The web uses one `career-vault` feature module because its executable
boundary rules prohibit private deep imports between product features.

### Account profile versus career record

The existing Phase 1 `user_profiles` aggregate remains the authority for account
display, locale, timezone, onboarding, and search/preferences such as target role,
location, work model, seniority, and industry. Its schema and `/api/v1/me`
contract are unchanged.

The Phase 3 `career_profiles` aggregate owns factual career-record presentation:
professional headline and summary, work authorization, and the ordered typed
career entities connected to evidence. Career Profile views may compose Phase 1
preferences through an explicit identity application query and link to their
existing editor. They do not duplicate or dual-write those fields.

### Evidence strength and lifecycle are separate

An evidence item has an independent lifecycle (`active`, `archived`, or deleted)
and strength (`Verified`, `Confirmed`, `Supported`, `Inferred`, or
`Unsupported`). Clients never supply the resulting strength directly.

| Transition                            | Authority and rule                                                                                                                                                                                   |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| create -> `Inferred`                  | Manual notes, parser classifications, incomplete answers, and structured claims without a directly preserved source span                                                                             |
| create -> `Supported`                 | Server validation proves the exact claim is present in an authorized, available source span and stores its immutable locator and digest                                                              |
| `Inferred`/`Supported` -> `Confirmed` | The authenticated owner reviews the normalized claim and explicitly attests to its scope; numeric claims also require value, unit, period, precision, attribution, and applicable comparison context |
| eligible state -> `Unsupported`       | The owner or deterministic policy rejects the claim, or a contradiction makes it unusable; the reason is recorded without copying free-form content into audit                                       |
| `Confirmed`/`Supported` -> `Verified` | Only a server-side `VerificationAuthority` decision with an allowlisted method, verifier reference, source, time, and scope                                                                          |
| material edit -> `Inferred`           | Editing a factual claim invalidates prior confirmation/verification; the immutable prior revision and transition remain                                                                              |

No independent verification provider is configured in Phase 3. Production user
APIs therefore cannot create `Verified` evidence. The internal authority port and
transition are implemented and tested so a later reviewed verifier can be added
without trusting a client flag. UI copy must explain that CareerOS verification
is a documented evidence process, not employer, credential, or background-check
certification.

Every material revision and strength transition is append-only and records owner,
actor/authority, previous and next state, reason code, request/trace identifiers,
and time. Audit metadata excludes evidence text, answers, filenames, URLs, and
attachment bytes.

### Deterministic downstream eligibility

Downstream modules obtain evidence only through an owner-scoped application query;
they never filter ORM rows or accept client-selected evidence as authoritative.
The query excludes evidence that is inferred, unsupported, archived, deleted,
conflicted, unauthorized, or backed only by an unavailable source. `Supported`
evidence is eligible solely for the exact preserved source scope. Numeric use
requires a `Confirmed` or `Verified` metric whose value/range, unit/currency,
period, baseline/comparator where applicable, approximation/precision, and
personal attribution are complete.

Phase 3 implements this boundary without a generation feature. Later role,
matching, and generation modules must consume it rather than inventing their own
state filter.

### Resume provenance and source deletion

Resume Health remains the owner of uploaded resumes, canonical snapshots, and
their deletion. `career_record` accesses them only through an explicit Phase 2
application query that rechecks the user and returns an immutable source DTO.

An imported proposal or evidence source copies the minimum durable provenance:
document and snapshot identifiers, revision/schema/parser version, block/source
span, source digest, and a bounded review excerpt. It does not foreign-key career
truth to a canonical snapshot whose deletion must remain possible.

Resume import and correction create reviewable proposals; they never apply a
profile mutation. Accept, edit-and-accept, and reject are explicit, versioned,
audited actions. Source availability is checked separately from stored strength.
Deleting the resume tombstones the live source from the evidence perspective but
does not delete or rewrite the career record. Source-only `Supported` evidence
then becomes ineligible until the owner independently confirms it or another
eligible source is connected.

Guest documents cannot propose durable career records until the existing explicit
claim flow transfers them to an authenticated account.

### Private evidence attachments

Evidence attachments have their own owner-scoped admission, processing, and
deletion records inside `career_record`. They use provider-neutral object storage,
malware scanning, and document extraction ports; the Resume Health module's ORM
models and infrastructure are not imported.

The Phase 3 policy accepts only bounded PDF and DOCX files. Upload uses randomized
private staging/quarantine keys and short-lived method/key/size/type-bound signed
`PUT` operations. Finalization rechecks owner, bytes, signature, and idempotency.
The restricted worker scans fail-closed, parses with the established archive/page/
character/resource limits, and commits clean state through durable jobs, outbox,
bounded retries, fencing, dead-letter visibility, and object-cleanup records.
Downloads require the same owner, a clean active attachment, and a short-lived
operation-specific signed `GET` or bounded authenticated stream with safe content
disposition. Permanent credentials and object keys never enter the public API.

Attachment presence does not itself make a claim `Supported`; an exact validated
source span or explicit confirmation is still required.

### Ownership, concurrency, conflicts, and deletion

Every Phase 3 row has a non-null `owner_user_id`. Repository operations query by
owner and identifier, nested links validate both ends in the same scope, and
cross-user/unknown identifiers have the same not-found behavior. Phase 3 serves
personal ownership only; optional organization context grants no implicit access.

Mutable aggregates use positive versions and strict quoted positive-int32
`If-Match` preconditions. Reorder locks and validates the complete owned set and
offers named move-up/move-down controls in addition to any future drag UI.
Achievement conversion and proposal/attachment finalization are idempotent.

Date precision is stored as year/month rather than inventing a day. Concurrent
roles and promotion sequences are presented as such. Gaps are neutral findings,
not negative evidence. Title/date/entity/metric contradictions create explicit
conflicts; the system never silently chooses a winner. Open conflicts exclude the
affected evidence from downstream use until an audited resolution.

Archive is reversible and always ineligible. Explicit delete removes private
content and attachment objects through the documented lifecycle while retaining
only the minimum redacted tombstone/audit needed to explain prior usage. Complete
account export/erasure orchestration, backup retention, and legal holds remain the
Phase 10 responsibility, but Phase 3 exposes owner-scoped inventory and deletion
operations so those workflows can include its data.

## Consequences

### Positive

- Evidence authority is deterministic and cannot be elevated by a client or model.
- Career truth survives source deletion without pretending that missing provenance
  remains eligible.
- Achievement conversion, evidence transitions, conflicts, and audit can commit
  atomically.
- Existing identity and Resume Health contracts remain backward-compatible.
- Later readiness and generation modules receive one tested eligibility boundary.

### Costs and risks

- The bounded context contains several related aggregates and needs internal
  ownership discipline to avoid becoming a generic data bucket.
- Copied provenance metadata and immutable revisions increase storage and erasure
  complexity.
- Attachment processing repeats durable job concepts while sharing only neutral
  provider adapters; extracting a standalone document service may be justified
  later by a third use case.
- Independent verification remains unavailable until a provider and operating
  process receive security/product approval.

## Alternatives considered

- **Separate profile, evidence, and achievement modules immediately:** rejected
  because confirmation/conversion/conflict/audit would require a distributed
  transaction or non-atomic cross-module writes without a deployment boundary.
- **Reuse `user_profiles` for career truth:** rejected because it mixes account
  preferences with evidence-backed facts and breaks existing contract semantics.
- **Foreign-key evidence directly to canonical resume rows:** rejected because
  Phase 2 deletion would either fail or silently cascade career provenance.
- **Let user confirmation mean Verified:** rejected because attestation and
  independent verification are materially different claims.
- **Reuse Resume Health upload tables for attachments:** rejected because it
  misclassifies supporting documents as resumes and couples module persistence.
- **Keep evidence content only in an attachment or model memory:** rejected because
  deterministic ownership, provenance, eligibility, conflict, and deletion checks
  would be impossible.

## Verification

Phase 3 cannot close until tests prove ownership and nested-link isolation, every
allowed/forbidden transition, numeric confirmation dimensions, source-span digest
and source-deletion behavior, stale/concurrent mutation handling, conflict and
audit behavior, private attachment admission/access/deletion, migration
round-trips, proposal-only imports, idempotent achievement conversion, and
desktop/mobile keyboard-accessible primary workflows. All Phase 2 verification
gates remain blocking regressions.
