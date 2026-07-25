# Architecture decision records

Architecture decision records (ADRs) capture consequential choices, their
context, and trade-offs. They describe accepted direction, not implementation
status; consult `PLANS.md` for current behavior.

## Index

| ADR                                                                   | Decision                                                                             | Status                                 |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | -------------------------------------- |
| [0001](0001-monorepo-and-runtime-topology.md)                         | Production-oriented monorepo with web, API, worker, and local data services          | Accepted; partially superseded by 0007 |
| [0002](0002-career-profile-and-evidence-as-source-of-truth.md)        | Career profile and evidence graph are the durable source of truth                    | Accepted                               |
| [0003](0003-deterministic-versioned-scoring.md)                       | Final scores are deterministic, versioned, and explainable                           | Accepted                               |
| [0004](0004-truth-locked-ai-and-immutable-user-controlled-changes.md) | AI output is schema-bound, grounded, reviewable, and versioned                       | Accepted                               |
| [0005](0005-ownership-scoped-tenancy-and-api-owned-sessions.md)       | Ownership-scoped data access with future organization tenancy and API-owned sessions | Accepted                               |
| [0006](0006-asynchronous-isolated-document-processing.md)             | Hostile document and render work runs as isolated, idempotent background jobs        | Accepted                               |
| [0007](0007-shared-modular-monolith-and-generated-contracts.md)       | Shared Python modular monolith, root uv workspace, and generated API contracts       | Accepted                               |
| [0008](0008-identity-sessions-and-same-origin-web-api.md)             | API-owned opaque sessions, same-origin web proxy, CSRF, and provider boundaries      | Accepted                               |
| [0009](0009-phase3-career-record-and-evidence-authority.md)           | Phase 3 career-record boundary, evidence authority, provenance, and attachments      | Accepted                               |
| [0010](0010-phase4-role-readiness.md)                                 | Phase 4 Role Explorer taxonomy, deterministic readiness, and evidence boundary       | Accepted                               |
| [0011](0011-phase5-job-match.md)                                      | Phase 5 Job Match, requirement matrix, and opportunity priority boundary             | Accepted                               |
| [0012](0012-phase6-change-studio.md)                                  | Phase 6 Change Studio provider gateway, grounding, and immutable change review       | Accepted                               |
| [0013](0013-phase7-resume-builder-export-verification.md)             | Phase 7 Resume Builder, immutable versions, verified export, and download intents    | Accepted                               |
| [0014](0014-phase8-application-workspace-and-packs.md)                | Phase 8 exact job/resume/evidence pins, grounded workspace packs, and no send/submit | Accepted                               |
| [0015](0015-phase9-interview-networking-growth-analytics.md)          | Phase 9 grounded interview, consent CRM, Career Health, and private analytics        | Accepted                               |

## Lifecycle

Use four statuses: Proposed, Accepted, Superseded, and Rejected. Do not edit an
accepted ADR to make history look different. Small clarifications may be appended
with a date; a changed decision gets a new ADR that links and supersedes the old
record.

An ADR is expected before adding a competing framework, changing the ownership or
source-of-truth model, changing score/grounding authority, altering production
queue/storage/session topology, adding a new external sensitive-data flow, or
weakening an established security boundary.
