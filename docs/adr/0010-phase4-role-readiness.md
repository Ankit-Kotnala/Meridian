# ADR 0010: Phase 4 Role Explorer and role readiness

- Status: Accepted
- Date: 2026-07-19
- Deciders: engineering

## Context

Phase 4 turns general role exploration into real product state. It must compare a
user-owned Career Record against a general role definition without requiring job
text, without inventing career facts, and without implying a hiring probability.
ADR 0009 requires downstream modules to consume Career Record through an
application boundary rather than reading evidence tables directly.

## Decision

Rezumi stores a versioned public role taxonomy, role definitions, and
competencies in `rezumi.modules.role_readiness`. The initial taxonomy is a
Rezumi-authored seed with explicit source/version/license metadata and stable
UUIDs. Future external taxonomy imports must create new taxonomy versions through
the same application/repository boundary rather than replacing existing analyses.

Role readiness analysis is deterministic code, engine
`role-readiness/1.0.0`, over a bounded owner-scoped readiness snapshot supplied by
`CareerRecordService.readiness_snapshot`. The role module does not query Career
Record tables or trust client-selected evidence. It persists the taxonomy,
engine/configuration/schema versions, feature hash, input snapshot, component
scores, competency results, and evidence links used for the explanation.

Saved roles, readiness analyses, competency results, evidence links, idempotency
records, and audit events are owner-scoped. Public taxonomy tables are not
user-owned. Mutations require authenticated session CSRF; saved-role updates and
deletes require `If-Match`; analysis requires `Idempotency-Key`.

The web implements Role Explorer as an authenticated feature module with loading,
empty, success, and error states; keyboard-named controls; semantic tables; score
disclaimers; saved-role notes; readiness history; and comparison for two or
three roles. It uses generated OpenAPI contracts and does not hardcode product
metrics.

## Consequences

- Historical analyses remain reproducible even if the seed taxonomy changes in a
  later version.
- Role readiness can explain demonstrated, listed, transferable, adjacent,
  missing, and unknown states while keeping hard gaps visible.
- Confirmed or Supported evidence may demonstrate role competencies according to
  eligibility and relevance, but evidence titles only are copied into role
  analysis rows; raw evidence text is not duplicated into audit or explanation
  tables.
- A general role readiness score is not a job match, employer ATS score, ranking,
  or employment prediction. Exact job requirements and URL-import security remain
  Phase 5.
