# ADR 0008: Identity sessions and same-origin web API

- Status: Accepted
- Date: 2026-07-15
- Deciders: Security, Product, and Engineering

## Context

ADR 0005 assigns authentication and authorization authority to FastAPI and
requires ownership-scoped access, Argon2id passwords, server-side revocation, and
secure browser cookies. Phase 1 must turn that direction into one deployable
contract without creating a second session authority in Next.js, exposing bearer
tokens to browser JavaScript, weakening the existing same-origin content security
policy, or requiring third-party credentials for local development and tests.

Registration, verification, recovery, OAuth, session management, onboarding, and
consent are security-sensitive workflows. They also need deterministic automated
tests and honest failure behavior when email, Redis, OAuth, or the database is
unavailable.

## Decision

The API is the only identity, session, and authorization authority. The web
application exposes a transparent, server-configured same-origin `/api/v1/*`
proxy. The proxy cannot select an arbitrary upstream, strips untrusted forwarding
and hop-by-hop headers, forwards only the cookie/origin/CSRF/content/correlation
headers needed by the API contract, preserves all `Set-Cookie` values, uses
manual redirect handling, and returns bounded, payload-free upstream failures.
Server-rendered route checks improve navigation but never replace API
authorization.

Passwords use Argon2id through a maintained library. Authentication material is
opaque, generated from a cryptographically secure random source, and stored only
as keyed digests. The API issues host-only cookies named `careeros_session` and
`careeros_refresh`; both are HTTP-only, `SameSite=Lax`, scoped to `/`, and Secure
outside explicit local development. A readable `careeros_csrf` cookie contains
no bearer authority. Unsafe requests require its value in `X-CSRF-Token`, a
session-bound digest match, and an exact allowed Origin. Authentication rotates
the session and CSRF material to prevent fixation.

Refresh tokens form a server-side lineage. Rotation locks the current generation,
marks it used, and issues its replacement transactionally. Reuse revokes the
session family and emits a safe audit event. Logout, logout-all, password reset,
account disablement, and explicit session revocation invalidate applicable
server-side records. Verification and reset secrets are short-lived, single-use,
hashed at rest, and delivered only through the configured email adapter.

Registration, resend, and recovery responses do not reveal whether an address is
registered. Password verification performs equivalent Argon2 work for unknown
accounts. Abuse controls use Redis atomic operations with redacted/HMAC-derived
keys and bounded windows. The API fails closed when those controls are required
but unavailable; deterministic in-memory adapters are limited to tests.

Google OAuth is an adapter. It uses exact callback URIs, one-time state, nonce,
and PKCE. Provider subject is the immutable external identity; matching email
alone never links an account. Local tests use an explicit deterministic adapter,
while production startup rejects incomplete OAuth, weak token-secret, insecure
cookie, or wildcard-origin configuration.

Phase 1 identity, profile, session, consent, organization extension, audit, and
onboarding state live in one `careeros.modules.identity` boundary. Individual
accounts do not receive synthetic organizations. Every owned lookup includes the
authenticated user and resource identifier; cross-user identifiers do not
disclose existence. Audit metadata is allowlisted and excludes email, passwords,
cookies, raw tokens, and request bodies.

## Consequences

### Positive

- The browser keeps a same-origin network policy and no persistent readable
  bearer token.
- One API authority owns rotation, revocation, reuse detection, audit, and
  ownership checks.
- Local SMTP and deterministic OAuth adapters exercise real application ports
  without production credentials or mock application state.
- Organizations, MFA, and stronger recent-auth requirements can extend explicit
  records and capabilities without changing the individual ownership model.

### Costs and risks

- Cookie authentication requires exact proxy, Origin, CSRF, SameSite, and Secure
  behavior across local and production ingress.
- Redis and email become explicit authentication dependencies with availability
  and fail-closed policy that operations must monitor.
- Opaque token rotation needs transactional locking and replay tests; application
  bugs can otherwise revoke valid sessions or accept a reused generation.
- A same-origin proxy must remain transparent enough for streaming future uploads
  while never becoming a general-purpose SSRF primitive.

## Alternatives considered

- **JWT access tokens in local storage:** rejected because browser scripts could
  read persistent bearer authority and immediate server-side revocation becomes
  harder.
- **Separate Next.js authentication:** rejected because it creates two session
  authorities and risks UI/API authorization drift.
- **Direct cross-origin browser calls:** rejected for the first-party web client;
  they add credentialed CORS complexity and weaken the existing same-origin CSP.
- **Email-only OAuth auto-linking:** rejected because a provider-email collision
  is not proof that an existing CareerOS account authorized the link.
- **Synthetic organization per user:** rejected because it obscures ownership
  semantics and complicates later membership authorization.

## Verification

Phase 1 tests cover enumeration resistance, dummy password verification, session
fixation, concurrent rotation and replay, logout/reset invalidation, hostile
Origin and CSRF values, abuse limits, expired/reused one-time tokens, OAuth state
and account collisions, anonymous and cross-user denial, safe audit content,
migration upgrade/downgrade behavior, same-origin proxy header handling, and the
complete browser registration-to-logout journey.
