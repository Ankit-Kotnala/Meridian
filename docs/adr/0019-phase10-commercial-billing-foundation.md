# ADR 0019: Fail-Closed Commercial and Billing Foundation

Status: Accepted
Date: 2026-07-26

## Context

CareerOS names four commercial plans, but product pricing, entitlement values,
quota values, payment provider, merchant account, tax behavior, and legal sales
copy are product-owner decisions. Inferring any of those values in application
code would create misleading public behavior and scatter authorization policy
across the frontend. Billing callbacks are also an unauthenticated internet
boundary where signature handling, replay, event ordering, ownership mapping,
and sensitive provider payloads require durable controls.

## Decision

Add `careeros.modules.commercial` as a provider-neutral bounded context and
migration `20260726_0014`.

- Persist the exact `free`, `job_hunt_sprint`, `pro`, and
  `coach_organization` plan identities in one catalog. Until the product owner
  supplies reviewed values, every plan is `owner_decision_required` and database
  constraints require price, provider reference, entitlements, and quotas to
  remain empty.
- A plan becomes purchasable only when its complete price tuple and provider
  reference are present. Domain and database validation reject partially
  configured or inferred commercial state.
- Keep checkout, portal, signed raw-webhook validation, and provider
  reconciliation behind `BillingProvider`. Production composition uses a
  disabled adapter. A credential-free deterministic adapter exists only for
  local and automated tests and authenticates raw webhook bytes with a bounded
  timestamped HMAC envelope.
- Persist owner-scoped billing customers and subscriptions. A customer reference
  never authorizes an account; the service maps it through durable ownership.
  One subscription per individual account is enforced at this phase.
- Persist the provider event identifier and raw-body SHA-256 before applying
  state. Exact replays return the existing result, a reused event identifier with
  different bytes conflicts, and monotonically older provider sequence values
  are retained as `ignored_stale` without reverting subscription state.
- Checkout and portal operations require owner authentication, CSRF, an
  allowlisted return origin, and an idempotency key bound to a request
  fingerprint. Provider session URLs must be HTTPS, uncredentialed, unfragmented,
  and unexpired.
- Audit only allowlisted action, provider name, durable identifiers, request ID,
  and trace ID. Raw webhook bodies, provider customer/subscription references,
  email, career content, and credentials are excluded.
- FastAPI remains the wire-contract authority. Commercial failures use stable,
  payload-free problem responses, and generated OpenAPI/TypeScript artifacts
  change in the same revision.

## Consequences

The repository can safely implement and test the commercial state machine
without pretending that live pricing or a payment provider has been selected.
Settings and public pricing must continue to show an unavailable/unconfigured
state until reviewed plan rows and a production provider adapter are supplied.

A future provider integration must satisfy the same raw-body limit, signature,
clock-skew, event-normalization, idempotency, ordering, reconciliation, redacted
telemetry, and failure contracts. It requires its own provider-security review;
this ADR does not authorize a merchant account or production billing traffic.

Coach/Organization billing remains individual-account scoped until Phase 10C
defines tenant ownership and purchaser/member capabilities. Plan entitlements
are authoritative commercial inputs, but Phase 10G owns their centralized
enforcement at quota and AI-cost boundaries.
