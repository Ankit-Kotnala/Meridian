# ADR 0005: Ownership-scoped tenancy and API-owned sessions

- Status: Accepted
- Date: 2026-07-14
- Deciders: Security and Engineering

## Context

Individual users must work immediately, while coaches, universities,
outplacement providers, and organizations may later collaborate. CareerOS stores
highly sensitive career documents and contacts, so a guessed UUID, selected
tenant header, signed object URL, or administrator role cannot imply access. The
web and API are first-party and can use secure browser cookies.

## Decision

Every user-owned row/object/job has explicit owner and, where applicable, tenant
scope. Service/repository APIs require an authorization context and query using
both that scope and resource ID. Organization membership/capability is an
extension layer; individuals do not require a fake organization. Workers and
signed-object operations recheck durable ownership.

FastAPI owns Phase 1 authentication. Passwords use Argon2id. Browser sessions use
secure HTTP-only cookies with CSRF/origin defenses and server-side session
records/rotating high-entropy refresh material hashed at rest. Google OAuth is an
adapter using state, nonce, PKCE, exact redirects, and safe account linking.

Administration uses distinct, least-privilege capabilities. It does not grant raw
resume access by default, and sensitive actions are audited.

## Consequences

### Positive

- Authorization is enforced at the data/service boundary rather than presentation.
- Organization collaboration can evolve without weakening individual ownership.
- Server-side session revocation, device/session management, and reuse detection
  are possible.
- HTTP-only cookies avoid persistent browser-readable bearer tokens.

### Costs and risks

- Every query, cache, search/vector lookup, queue task, export, and object path
  must preserve scope; omissions are critical defects.
- Cookie sessions require correct CSRF, SameSite, domain, and CORS policy.
- Organization role/delegation design needs a later capability matrix and tests.
- API-owned auth increases security maintenance compared with a hosted identity
  service; maintained cryptographic/auth libraries remain mandatory.

## Alternatives considered

- **Trust UUID unpredictability:** rejected; UUIDs are identifiers, not access
  controls.
- **Require an organization for every person:** rejected as artificial complexity
  and a source of confused-deputy bugs for the individual product.
- **Store bearer tokens in local storage:** rejected due to script-readable token
  theft and weaker central revocation semantics.
- **Let Next.js own separate auth state:** rejected to avoid split authorization
  truth and mismatched API sessions.

## Implementation notes

Phase 1 introduces identity/session/consent/audit models and anonymous/cross-user
tests. Each later data phase adds ownership tests. PostgreSQL row-level security
may be added as defense in depth after connection/pooling/tenant-context behavior
is proven; it does not replace application authorization and would require a new
or superseding ADR.
