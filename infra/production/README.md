# Production handoff boundary

This directory contains the non-secret, provider-neutral production contract
template. It intentionally contains no Terraform, credentials, remote state, or
claim that a cloud topology has been selected.

Read [the production operations runbook](../../docs/production-operations.md)
before using the `Release candidate` workflow.

## Required GitHub environment

Create a protected environment named `production` and configure:

- required reviewers from release, security, privacy, and operations;
- prevent self-review;
- deployment branches restricted to `main`;
- no routine administrative bypass; and
- an environment secret named `PRODUCTION_DEPLOYMENT_CONTRACT_JSON`.

The secret value is a completed copy of
`deployment-contract.template.json`. The committed template is expected to fail
validation. Never put credentials or secret values in the contract.

`PACKAGE_ONLY` creates the immutable candidate and evidence. `HANDOFF` is eligible
only from `main`, waits at the protected environment, and validates owner
decisions plus candidate checksums. It deliberately does not deploy to an
unselected provider.

Provider-specific infrastructure belongs in a later reviewed change after the
provider, region, services, data residency, state backend, recovery policy,
operator model, and rollback plan are approved. That change must add its own ADR
and cannot weaken this contract.
