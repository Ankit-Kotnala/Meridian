# ADR 0016: Semantic Resume and Parser Isolation

Status: Accepted
Date: 2026-07-25

## Context

The historical Phase 2 slice safely admitted PDF and DOCX files, preserved
generic canonical blocks, and produced deterministic Resume Health v1 reports.
It did not yet provide the typed contact, experience, education, project, skill,
and certification model required by later evidence workflows. Its parser timeout
wrapped `asyncio.to_thread`, so a timed-out library call could continue until the
worker or container stopped. Text extraction, layout analysis, and semantic
classification also lacked independently replaceable boundaries.

Typed values cannot silently replace source text. Parser guesses, user
corrections, user-added facts, removals, and reclassifications have different
truth and provenance meaning. Existing v1 snapshots must remain readable and
upgrade through an explicit review action.

## Decision

### Immutable source and typed semantic sidecar

- Canonical resume schema `canonical-resume/2.0.0` retains immutable
  `sourceSections` and adds a versioned `CanonicalSemantics` sidecar.
- Semantic entities use a closed kind and field vocabulary. Parser-derived
  fields carry deterministic IDs, confidence, review state, date precision where
  relevant, and one or more exact source anchors containing block ID, page,
  character offsets, and source SHA-256.
- User-added values are explicit, have no source anchor, and never imply that the
  parser or uploaded file supplied them. Corrected values retain the original
  anchor so the extracted basis remains inspectable.
- Confirm, correct, add, remove, and reclassify are typed application operations.
  A review creates an immutable successor snapshot with optimistic concurrency
  and a redacted audit event. Confirming no changes is an explicit operation, not
  inferred from an empty request.
- Legacy v1 snapshots remain readable. The first typed review uses the local
  parser provider to create a v2 successor; it never mutates historical JSON.

### Replaceable parsing boundaries

- `DocumentTextExtractor`, `LayoutAnalyzer`, `ResumeParserProvider`,
  `MalwareScanner`, and `OcrProvider` are inward-facing ports.
- Deterministic local text, layout, and semantic adapters are the credential-free
  baseline. Future commercial adapters must implement the same bounded contracts
  and cannot change source-of-truth or review rules.
- Layout analysis flags table-heavy, multi-column, header/footer, reading-order,
  and bidirectional-control risks. Header/footer text and hidden Unicode controls
  are excluded or sanitized before semantic input.

### Killable parser process

- The worker uses `IsolatedDocumentExtractor`, which launches the local parser in
  a dedicated child process with an allowlisted JSON request/result contract.
- Source and result paths must remain below the configured private temporary
  root. Standard input/output are disabled, output size is bounded, and only safe
  error codes cross the boundary.
- Timeout force-kills and awaits the child before the temporary workspace is
  removed. POSIX children also receive bounded CPU, address-space, and output
  limits; container controls remain the outer defense.

### Resume Health v2

- Final scoring remains deterministic fixed-point code with no LLM authority.
  Engine `resume-health/2.0.0`, configuration `resume-health-default/2`, and
  feature schema `resume-health-features/2` add semantic breadth, exact
  source-anchor coverage, explicit review coverage, and date-precision coverage.
- Historical analyses retain their original versions and values. Missing semantic
  data is neutral rather than treated as perfect or fabricated evidence.

## Consequences

- Canonical JSON grows, but the existing bounded JSONB snapshot and artifact size
  limits remain sufficient; no schema migration is required.
- Later Career Record ingestion can consume typed reviewed values without
  querying parser tables or treating generic blocks as factual authority.
- Local layout analysis is intentionally conservative and warning-oriented. It
  does not claim rendered DOCX page geometry or perfect two-column reconstruction.
- OCR remains an optional disabled port. Image-only input still produces
  insufficient data unless an enabled provider supplies bounded extraction.

## Verification

- Domain, service, API, and UI tests cover serialization, legacy reads,
  deterministic IDs, source anchors, date precision, every typed review
  operation, immutable successors, optimistic concurrency, and cross-owner
  denial.
- Parser tests prove child-process timeout termination and cleanup plus malformed,
  disguised, encrypted, archive, macro, expansion, table, multi-column,
  header/footer, date-locale, concurrent-role, unusual-font, bidirectional,
  long-document, and image-only behavior.
- OpenAPI and generated TypeScript contracts change with the API. Phase closeout
  requires repository gates, integration/E2E coverage, container policy, and the
  security scan recorded in `PLANS.md`.
