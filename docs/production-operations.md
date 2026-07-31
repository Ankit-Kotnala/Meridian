# Production release and recovery operations

This runbook defines the provider-neutral release boundary implemented by
CareerOS. It does not claim that local Compose is production infrastructure or
that an unselected cloud, region, registry, queue, backup service, monitoring
service, or legal policy exists.

## Release authority and separation of duties

Production handoff requires all of the following:

1. A commit on `main` that passed required CI.
2. A release-candidate bundle built from that exact 40-character commit SHA.
3. SHA-256 checksums, SPDX JSON SBOMs, vulnerability scans, and GitHub artifact
   attestations for the four deployable images.
4. An approved change ticket and a completed deployment contract.
5. A GitHub `production` environment configured with required reviewers,
   prevent-self-review, `main`-only deployment branches, and no administrative
   bypass for ordinary releases.
6. Separate release, security, privacy, and operations approvals in the
   deployment contract.
7. A provider-specific operator who deploys only the recorded immutable image
   digests.

The repository intentionally does not contain speculative Terraform or a
provider deploy command. Provider, region, data residency, services, registry,
network topology, secret manager, and operator identities must be approved
before that implementation can be reviewed.

## Deployment contract

Start from
`infra/production/deployment-contract.template.json`. The template is
deliberately invalid. It contains no credentials and must remain safe to commit.
The completed JSON is stored as the protected environment secret
`PRODUCTION_DEPLOYMENT_CONTRACT_JSON`; it must not be committed, logged, placed
in an artifact, or copied into a pull request.

The validator rejects:

- unknown or missing fields;
- placeholders, local/test URLs, control characters, and secret-like fields;
- a release SHA, change ticket, migration head, or candidate checksum that does
  not match the workflow inputs;
- unbounded or malformed topology, recovery, canary, and retention values;
- missing PITR, MFA, restore, load, monitoring, alert, penetration-review,
  key-rotation, provider-erasure, rollback-test, or on-call evidence;
- any open critical or high security finding; and
- missing release, security, privacy, or operations approval.

Run an offline validation without printing the contract:

```sh
python scripts/release/validate_deployment_contract.py \
  --file /secure/path/deployment-contract.json \
  --expected-release-sha "$RELEASE_SHA" \
  --expected-change-ticket "$CHANGE_TICKET" \
  --expected-candidate-checksum "api=sha256:$API_ARCHIVE_SHA256" \
  --expected-candidate-checksum "worker=sha256:$WORKER_ARCHIVE_SHA256" \
  --expected-candidate-checksum "web=sha256:$WEB_ARCHIVE_SHA256" \
  --expected-candidate-checksum "web-edge=sha256:$WEB_EDGE_ARCHIVE_SHA256"
```

A successful command emits only a canonical contract fingerprint.

## Candidate packaging and provenance

Run the `Release candidate` workflow manually against the exact revision.
`PACKAGE_ONLY` builds the API, worker, web, and web-edge images from their pinned
Dockerfiles; archives them; emits checksums and SPDX JSON SBOMs; creates
provenance and SBOM attestations; and uploads one 14-day candidate bundle.

Before handoff:

1. Download the bundle from the workflow run.
2. Run `sha256sum --check SHA256SUMS`.
3. Verify the attestations against the repository and expected workflow identity
   with `gh attestation verify`.
4. Confirm that the deployment contract contains those exact candidate archive
   checksums and the immutable registry digests selected for deploy and rollback.
5. Confirm the production upload origin used at web build time.

Artifact attestations establish build identity and integrity; they do not replace
code review, vulnerability response, registry admission policy, or an external
penetration review.

## Provider deployment sequence

The approved provider implementation must preserve this order:

1. Validate registry digests, topology, trusted proxy CIDRs, secret references,
   capacity, maintenance window, restore evidence, and current database head.
2. Confirm an encrypted backup/PITR recovery point and the tested rollback image
   digests before changing production.
3. Deploy the migration runner as a single fenced operation. The application
   expects the one Alembic head recorded by the deployment contract.
4. Deploy API and web canaries at the approved percentage. Keep background
   consumers constrained until schema and health probes pass.
5. Probe API liveness/readiness, same-origin web health, the scheduler, worker
   ping, Redis admission, object access, and safe queue execution.
6. Observe for the contract’s full canary window. Compare error, latency,
   saturation, dead-letter, database, Redis, object-store, and billing-webhook
   signals to the approved baseline.
7. Expand gradually, then release worker concurrency. Record final image digests,
   migration state, timestamps, approvers, and dashboards in the change record.

No step may use an unpinned `latest` deployment reference.

## Rollback and forward repair

Stop the rollout when health, authorization, grounding, privacy, budget, queue,
or data-integrity gates fail. Disable new side effects, preserve evidence, and
restore the recorded rollback application digests.

Database downgrade is not automatic. Prefer a reviewed forward repair whenever
new writes could be incompatible with the prior schema. Use a migration downgrade
only when the change record explicitly proves compatibility, the backup recovery
point is available, and the migration owner authorizes it. The local gate proves
`20260727_0019 -> 20260727_0018 -> 20260727_0019`; it does not prove production
data can always be downgraded without a case-specific review.

After rollback, verify ownership isolation, session invalidation, queues,
scheduled jobs, object access, billing ingestion, account privacy operations,
and the administration audit chain before reopening traffic.

## Backup and restore

The selected production services must provide:

- encrypted automated database backups and point-in-time recovery;
- private versioned object backups with lifecycle enforcement;
- backup access separated from application credentials;
- a documented failure domain and provider/data-residency boundary;
- retention and backup-deletion expiry matching the approved privacy policy;
- monitoring for failed, stale, or unverified backups; and
- periodic isolated restore drills within the approved RPO/RTO.

Each production drill restores into isolated, non-routable targets; verifies the
expected migration head, schema/table inventory and record counts, object count
and byte digests, application probes, and authorization checks; records bounded
evidence; then removes the drill targets.

The local equivalent uses randomized, prefix-guarded PostgreSQL and MinIO targets:

```sh
python scripts/recovery/verify_local_restore.py \
  --confirm-local-compose \
  --repository-root . \
  --output .data/release-evidence/recovery.json
```

It never restores over the source database or bucket. Local evidence validates
the implementation path, not provider backup durability.

## Capacity and soak evidence

The read-only load gate requires credential-free HTTPS by default, rejects
redirects, caps response size and samples, and records safe aggregate evidence.
Use `--allow-http` only for loopback verification. A sustained gate should set a
target rate so it tests the service rather than exhausting the load generator.

```sh
python scripts/release/load_smoke.py \
  --base-url https://production.example \
  --path /health \
  --concurrency 8 \
  --soak-seconds 300 \
  --target-requests-per-second 100 \
  --max-p95-ms 500 \
  --max-error-rate 0 \
  --min-requests-per-second 90 \
  --output load-evidence.json
```

Production thresholds must come from approved capacity objectives and monitoring,
not from these example values. Side-effecting or user-owned routes require a
separate synthetic tenant, explicit cleanup, and a reviewed test plan.

## Monitoring and incident response

Alert ownership and routing are deployment-contract inputs. At minimum monitor:

- API/web availability, latency, error and rejection rates;
- trusted-hop/BFF signature failures and platform limiter availability;
- AI reservation exhaustion, concurrency leases, and provider usage-schema
  failures without exposing user prompts;
- PostgreSQL connections, locks, replica/PITR lag, migrations, and backup age;
- Redis availability, persistence, memory, eviction, and failover;
- queue age, retries, leases, scheduler health, dead letters, and worker resource
  saturation;
- object-store failures, quarantine/scanner failures, and lifecycle drift;
- billing webhook signature/order/reconciliation failures;
- privacy export/deletion backlog and backup-erasure deadlines; and
- administration audit-chain verification and unauthorized attempts.

Incidents use the least-privilege operator capabilities already implemented.
Do not query or paste raw resumes, evidence, tokens, signed URLs, or provider
payloads into tickets or chat. Record request/trace IDs and redacted identifiers,
contain the affected capability, preserve audit evidence, notify the approved
owners, and follow the legal notification decision tree.

## Secret and signing-key rotation

Bearer/signing key families use current-plus-previous rollout:

1. Deploy the new current value and move the old current value to previous.
2. Verify new issuance and both-key validation.
3. Wait the maximum owning token/capability lifetime.
4. Remove the previous value and verify rejection.

Do not rotate AI usage or administration-audit HMAC peppers with this procedure.
They require a drain/reconciliation or retention-boundary plan because changing
them splits budget or audit pseudonym history. Provider credentials, database
roles, object keys, SMTP, billing, registry, and GitHub environment secrets need
provider-specific dual-control runbooks and evidence identifiers.

## Open production blockers

Production deployment remains blocked until owners approve and configure:

- provider, region, data residency, network/trusted-hop, registry, database,
  Redis/queue, object storage, scanner/parser isolation, and secret manager;
- pricing/provider accounts and legal privacy/retention/deletion terms;
- RPO/RTO, capacity objectives, monitoring, alert routes, and on-call schedule;
- operator identity, MFA, provisioning, recertification, and audit export/WORM
  retention;
- external penetration review and closure of all critical/high findings; and
- the protected GitHub environment, its reviewers, and its contract secret.

These are deployment authorities and external evidence, not values the codebase
can safely invent.
