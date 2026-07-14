# ADR 0003: Deterministic, versioned scoring

- Status: Accepted
- Date: 2026-07-14
- Deciders: Product, Data, and Engineering

## Context

CareerOS needs Resume Health, Role Readiness, Requirement Coverage, Evidence
Strength, Application Readiness, and related measures. Letting a language model
emit a number would be nondeterministic, difficult to explain, easy to manipulate,
and likely to be confused with an employer's ATS or hiring probability.

## Decision

Final numeric scores are calculated by deterministic code from validated,
structured features under immutable versioned configurations. Models may propose
classifications or extracted candidates, but source spans/schema validation turn
them into inputs and the model never supplies or overrides the final score.

Every score stores input snapshot, engine/configuration version, fixed-precision
raw value, displayed rounding, component/feature contributions, hard gaps,
missing-data handling, warnings, and computation time. Hard requirements are
displayed separately. Historical analyses are not recomputed in place.

Every relevant view carries the canonical internal-readiness disclaimer. Scores
are never described as employer ATS results, hiring probabilities, guarantees, or
causal outcome measures.

## Consequences

### Positive

- Scores are reproducible, testable with golden fixtures, and explainable.
- Formula changes are auditable and trend breaks can be represented honestly.
- The product can reject keyword gaming and keep mandatory gaps visible.
- Provider/model upgrades do not silently change final arithmetic.

### Costs and risks

- Feature design and calibration require disciplined product/data review.
- Determinism does not guarantee validity or fairness; proxy and language/locale
  risks still require testing and user research.
- Versioned scores add storage and comparison complexity.
- Extracted feature uncertainty must be exposed rather than hidden by precision.

## Alternatives considered

- **Ask an LLM for a 0–100 score:** rejected for nondeterminism, opacity, and
  misleading authority.
- **One universal formula for all analyses:** rejected because general document
  health, role fit, and exact job coverage answer different questions.
- **No number, findings only:** potentially less misleading, but numbers help
  summarize progress when paired with components/disclaimer. Individual product
  studies may still choose categorical output for Opportunity Priority.

## Implementation notes

The normative formulas, proposed match credits, missing-data behavior, rounding,
versioning, and tests are in `docs/scoring-methodology.md`. Phase 0 contains no
real score. Engines arrive in Phases 2, 4, and 5 and cannot exit without unit,
property, golden, provenance, hard-gap, and accessible-explanation tests.
