# ADR 0002: Career profile and evidence as the source of truth

- Status: Accepted
- Date: 2026-07-14
- Deciders: Product and Engineering

## Context

A resume is incomplete, formatted for one context, and often contains ambiguous
or unsupported shorthand. Making an uploaded resume the master record would cause
tailored versions, application answers, networking copy, and interview stories to
drift. CareerOS also promises that it will not invent career information.

## Decision

The durable source of truth is a structured career profile connected to a
provenance-rich evidence graph. Uploaded resumes and user answers are sources that
can propose profile/evidence records; they are not automatically authoritative.

Each factual output claim links to eligible evidence and source provenance.
Evidence state (Verified, Confirmed, Supported, Inferred, Unsupported), parser/
model confidence, user confirmation, and independent verification remain
separate. Resumes, cover letters, application answers, bios, messages, and
interview stories are versioned derived outputs tied to exact profile/evidence
snapshots.

## Consequences

### Positive

- One correction can inform future outputs without silently rewriting history.
- Grounding, conflict detection, requirement matching, and interview defense are
  explainable through stable links.
- Multiple resume variants do not become competing masters.
- Data export and deletion can describe sources, derivations, and usage.

### Costs and risks

- The evidence graph and source-span model are more complex than storing resume
  text.
- Import UX must ask users to resolve uncertainty rather than promising magical
  completion.
- Evidence state language can be misunderstood as third-party background
  verification and needs precise product copy.
- Snapshot/version storage increases data-lifecycle and deletion complexity.

## Alternatives considered

- **Latest resume is canonical:** simple but loses provenance, conflicts across
  variants, and encourages unsupported reuse.
- **Free-form profile text:** flexible but difficult to authorize, compare,
  ground, score, and validate consistently.
- **Model memory as source of truth:** nondeterministic, opaque, provider-bound,
  and unacceptable for factual career claims.

## Implementation notes

Phase 2 introduces the canonical parsed resume; Phase 3 introduces the career
profile, evidence entities/states, source spans, confirmation, and usage links.
Phase 6 enforces claim-ledger grounding. Historical outputs remain immutable even
when source evidence is later corrected or archived; the product surfaces the
conflict rather than rewriting the past.
