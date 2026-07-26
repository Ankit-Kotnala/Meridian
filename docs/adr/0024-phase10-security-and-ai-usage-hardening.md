# ADR 0024: Central request admission, AI usage reservation, and parser isolation

Status: Accepted  
Date: 2026-07-27

## Context

CareerOS already had feature-specific authorization, upload limits, session
controls, grounding validation, and durable jobs. Phase 10G still required a
coarse platform admission boundary, enforceable live-AI cost ceilings, consistent
browser response policy, safer hostile-document parsing, and an operable
credential-rotation path.

Commercial plan prices and entitlements, a live AI provider, production edge
topology, operator MFA, and an external penetration-testing vendor remain owner
or deployment decisions. The application must not invent those values or weaken
controls when they are absent.

## Decision

1. Every `/api/v1` request passes a coarse Redis-backed platform limiter before
   route execution. Read and mutation buckets are separately bounded. Staging
   and production fail closed when the limiter or the authenticated BFF source
   signal is unavailable; development and tests may use their direct peer.
2. The trusted edge removes client-selected forwarding headers, derives the
   source only from its socket peer, and signs that source for the API. The API
   does not trust an arbitrary `Forwarded`, `X-Forwarded-For`, or `X-Real-IP`
   value.
3. A live HTTP AI provider cannot start without explicit per-call reservations,
   monthly token and cost ceilings, request rate, concurrency, and lease limits.
   One Redis Lua transaction admits the rate, concurrency lease, and both
   calendar-month budgets atomically.
4. AI ownership keys are context-separated HMAC pseudonyms. The provider wrapper
   reserves worst-case usage before network I/O and refunds only when the live
   provider returns bounded, schema-valid token and cost usage. Missing,
   malformed, or over-reservation usage fails safely and retains the full
   reservation.
5. API responses receive deny-by-default API CSP, no-store defaults, framing,
   MIME-sniffing, referrer, permissions, and cross-domain restrictions. The web
   edge overwrites security-policy headers from upstream and enables HSTS plus
   insecure-request upgrading only when TLS termination is explicitly configured.
6. Resume and evidence-attachment parsing run in killable child processes with a
   credential-free environment, bounded request/result files, closed inherited
   descriptors, temporary-workspace cleanup, timeouts, resource limits where
   supported, and a Python audit hook denying standard-library network and child
   process creation.
7. Session, account-operation, guest-capability, organization-invitation, and BFF
   source-signing secrets support one previous value. New values are used for
   issuance; current and previous values are accepted for verification during a
   bounded rotation window. Blank previous values normalize to absent, weak
   values fail validation, and current/previous equality is rejected.
8. Secret rotation is deploy-current-plus-previous, wait for the owning maximum
   token/capability lifetime, then remove previous. Rotation values are never
   logged or returned. The AI usage pseudonym pepper and administration audit
   pepper are not silently rotated because changing their derived identifiers
   can split active budget or audit identity history.

## Consequences

- Live AI remains disabled until the owner supplies a provider and reviewed
  ceilings. Deterministic local/test operation does not pretend to incur provider
  usage.
- Calendar-budget state is operational Redis state, not a billing ledger. Redis
  persistence, high availability, monitoring, and recovery are Phase 10H
  deployment requirements. Unavailability fails closed for live AI.
- The edge CSP retains framework-required inline script/style support for the
  current Next.js build. It blocks script attributes, third-party origins,
  framing, objects, and unlisted connections; adopting per-request nonces is a
  future defense-in-depth change that requires framework-wide rendering work.
- The Python audit hook and worker container controls reduce attack surface but
  are not a kernel security boundary. A production parser topology still needs
  patch ownership, isolated compute/network policy, resource monitoring, and a
  kill switch.
- BFF source signing is correct for the current direct edge-to-API topology. A
  production load balancer/CDN requires an explicit trusted-hop policy; arbitrary
  forwarding headers remain prohibited.
- Operator MFA is not claimed. No operator exists by default, authority cannot be
  granted over HTTP, and recent authentication is required for the current admin
  mutation. Production operator enablement remains blocked until the owner
  approves MFA and provisioning/recertification policy.
- Automated adversarial, configuration, integration, dependency, image, and
  header checks are necessary evidence, but they are not an independent
  penetration test. External review remains a release-approval input.
