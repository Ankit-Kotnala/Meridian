# ADR 0025: Provider-neutral release evidence and protected handoff

Status: Accepted
Date: 2026-07-27

## Context

Phase 10H requires production infrastructure, recovery proof, load evidence,
protected CI/CD, and rollback controls. No owner-approved cloud, region, data
residency, registry, managed database, Redis/queue, object store, monitoring
provider, RPO/RTO, or operator identity exists in the repository. Creating
Terraform or a deploy command for an invented topology would misrepresent
production readiness and could make unsafe data, privacy, and security decisions.

Local Compose remains useful evidence but is not a production topology.

## Decision

1. CareerOS packages four immutable candidate image archives from an exact commit:
   API, worker, web, and web-edge. The release workflow emits SHA-256 checksums,
   SPDX JSON SBOMs, provenance attestations, SBOM attestations, and a bounded
   workflow artifact.
2. CI keeps pinned actions and base images, secret/dependency/container scans,
   current migration upgrade/downgrade/upgrade proof, live Redis integration, and
   offline fail-closed release/recovery control tests.
3. A strict, non-secret-schema deployment contract binds the selected commit,
   change record, migration head, candidate checksums, deployment and rollback
   image digests, topology, trusted proxies, recovery objectives/evidence,
   security/privacy evidence, load/monitoring/on-call evidence, and four approval
   roles. Unknown fields, placeholders, secret-like keys, open critical/high
   findings, or missing evidence fail closed.
4. The contract value is supplied only after a protected GitHub `production`
   environment gate. Handoff is eligible only from `main` and does not execute an
   unselected provider deployment.
5. Recovery proof restores PostgreSQL and object data into randomized isolated
   temporary targets, compares the migration head, exact table counts, and object
   byte manifests, and removes the targets. The checked-in verifier is restricted
   to confirmed local Compose; production restore evidence remains provider-owned.
6. Load/soak evidence is read-only, bounded, redirect-free, HTTPS by default, and
   optionally target-rate paced. Threshold failures retain machine-readable
   aggregate evidence.
7. Provider-specific infrastructure is deferred until owners approve the
   topology, data boundary, state backend, recovery policy, and operator model.
   That implementation requires a follow-up ADR, rollback plan, and protected
   environment review.

## Consequences

- The repository can produce reviewable, checksum-bound release artifacts and
  prove its local restore/load mechanisms without pretending that production
  exists.
- Artifact attestation availability depends on the repository’s GitHub plan.
  The release workflow fails rather than silently omitting provenance when the
  required service is unavailable.
- A configured GitHub environment is still an external control. Until required
  reviewers and the contract secret exist, `HANDOFF` fails closed.
- Local table-count and object-digest equivalence do not prove production backup
  encryption, cross-failure-domain durability, PITR, or RPO/RTO. Those remain
  mandatory contract evidence.
- No production deployment is authorized until provider selection, legal and
  privacy policy, operator MFA/provisioning, monitoring/on-call, independent
  penetration review, and critical/high finding closure are approved.
