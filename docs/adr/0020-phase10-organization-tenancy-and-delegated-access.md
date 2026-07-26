# ADR 0020: Organization Tenancy and Explicit Delegated Access

Status: Accepted
Date: 2026-07-26

## Context

Phase 1 reserved organization and membership tables so individual accounts could
later join an organization without requiring a synthetic tenant. Phase 10 needs
Coach/Organization collaboration, but a client-supplied organization identifier
or broad role would become a confused-deputy path into raw resumes, evidence,
contacts, exports, and private notes. Invitations also cross an email boundary,
and asynchronous delivery must not expose a bearer token in an API response or
lose work between a database commit and broker publication.

## Decision

Migration `20260726_0015` expands the existing Phase 1 tables and adds
`careeros.modules.organizations` as the tenant-authority bounded context.

- Individual accounts remain valid with no organization membership. The server
  derives organization access from an active durable membership on every request;
  no tenant header, route identifier, or billing reference grants authority.
- Roles are `owner`, `admin`, `coach`, and `member`. The server maps each active
  role to explicit capabilities. Suspension removes all capabilities immediately,
  and an owner cannot be suspended through the member operation.
- Owners and admins may manage the organization or roster according to their
  capabilities. Coaches and members can see only their own roster record; list
  endpoints never turn membership into directory access.
- Email invitations store a normalized mailbox only for delivery, a keyed digest
  for equality checks, and a keyed token digest after delivery. Raw invitation
  tokens are never persisted or returned from the invitation-creation API.
  Acceptance binds the token to the currently active account's normalized email,
  expiry, status, and exact organization.
- Invitation creation and its delivery outbox row are committed atomically.
  Phase 10D owns leasing, retry, dead-letter, and actual email delivery. Until
  then the public operation truthfully reports `queued`.
- A subject may grant a coach or admin one expiring, revocable summary-level
  scope at a time. The only scopes are career-profile, resume-health,
  role-readiness, application-status, career-growth summaries, and collaboration
  comments. Raw resumes, evidence text, private notes, contacts, object keys,
  download intents, and exports are intentionally not grantable.
- Every delegated authorization rechecks both active memberships, the grantee
  role, grant status, grant expiry, organization, subject, grantee, and scope.
  Knowing a grant or resource UUID never authorizes access.
- Organization creation, invitations, acceptance, and grant creation use
  operation-bound idempotency records. Versioned updates, suspension, and
  revocation use optimistic concurrency. Database uniqueness and partial indexes
  close concurrent duplicate-invitation and duplicate-active-grant races.
- The built-in ownership, membership, grant, and invitation limits are abuse
  safety caps, not product entitlements or commercial quotas. Product-owner
  commercial values remain fail-closed under ADR 0019.
- Audit records contain durable identifiers, allowlisted actions, role/scope
  labels, request ID, and trace ID. Invitation email, token material, career
  content, and external references are excluded.

## Consequences

Coach/Organization collaboration has a durable least-privilege authority model,
while existing individual workflows remain unchanged. Product modules may use
the explicit delegated-scope application query; they must not query organization
tables or infer access from roles themselves.

The `coach_organization` commercial plan remains unpurchasable while pricing,
provider, entitlements, quotas, tax, and legal decisions are unresolved.
Organization-scoped billing may bind to this tenant authority in a later reviewed
commercial change; this ADR does not infer purchaser, seat, or billing policy.

Invitation delivery is not complete until Phase 10D consumes the durable outbox
with bounded leases, retries, and dead-letter recovery. Organization aggregation
and collaboration endpoints must still be added feature by feature and may expose
only the exact scope authorized by this ADR.
