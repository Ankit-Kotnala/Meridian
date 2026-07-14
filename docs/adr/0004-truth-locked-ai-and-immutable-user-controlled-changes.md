# ADR 0004: Truth-locked AI and immutable user-controlled changes

- Status: Accepted
- Date: 2026-07-14
- Deciders: Product, Security, and Engineering

## Context

Language models can improve extraction and writing but can also invent metrics,
elevate ownership, obey malicious instructions in resumes/jobs, drift across
documents, and produce unsafe output. Silent rewriting would undermine the core
user-control and factual-integrity promises.

## Decision

All AI capabilities go through an environment-selected provider gateway with a
deterministic fake for tests. Inputs are minimal and untrusted document content is
separated from fixed policy. Outputs use strict typed schemas and are rejected on
malformation.

Generated text carries an atomic claim ledger. Before display/action, a
deterministic verifier checks authorization, evidence eligibility, facts,
numbers, entities/dates, technologies/credentials, contribution/causality, and
cross-document consistency. Unsupported output is blocked or becomes a neutral
clarifying question.

Material changes are structured operations with original/suggested text, diff,
reason, evidence, requirement, risk, and confirmation status. The user can
accept, reject, edit, regenerate, undo/redo, lock, and restore. Final user edits
are revalidated. Acceptance creates a new immutable version; exported/published
versions never mutate.

## Consequences

### Positive

- Provider capability cannot bypass evidence or user authority.
- Every displayed suggestion is explainable and auditable.
- Deterministic fakes make adverse and regression testing reproducible.
- Immutable versions support restore, pinned applications, and export verification.

### Costs and risks

- Claim decomposition and meaning-preservation checks are complex and may reject
  useful ambiguous prose.
- Semantic verification cannot be perfect; high-risk claims still need explicit
  user confirmation.
- Storing provenance/version history increases privacy and deletion obligations.
- Provider retries and regeneration need idempotency and cost control.

## Alternatives considered

- **Direct chat-generated replacement text:** rejected because provenance, diffs,
  stable targets, and deterministic validation are lost.
- **User acceptance is sufficient grounding:** rejected because the product would
  still present unsupported suggestions and invite accidental fabrication.
- **Auto-apply changes above a model confidence threshold:** rejected because
  model confidence is not evidence and material changes require user control.

## Implementation notes

`docs/ai-grounding-policy.md` is the normative policy. Phase 3 supplies evidence,
Phase 5 source-spanned requirements, and Phase 6 the gateway, schemas, grounding,
Change Studio, immutable resume versions, and adversarial tests. Phase 0 makes no
AI or grounding implementation claim.
