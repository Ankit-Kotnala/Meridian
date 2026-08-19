# ADR 0019: Activation-first workspace and the assisted application supply chain

- Status: Accepted
- Date: 2026-08-17
- Deciders: Engineering, Product

## Context

Every capability needed to turn one uploaded resume into a reviewed career
record already exists: Resume Health parses and scores a document, canonical
review confirms uncertain fields, and `career_record` converts a reviewed
snapshot into typed and semantic import proposals the user accepts. Role
readiness computes competency gaps, `career_growth` tracks development items
with a `learning` kind, `job_match` analyses a saved job against the record,
and `application_workspace` tracks stages, tasks, and packs.

None of that is visible from the authenticated home. A new account lands on a
workspace of zeros and fifteen sidebar destinations with no indication that the
product does anything until a resume exists. The capability chain is
implemented but not orchestrated, so the workspace reads as inert.

Product also intends to extend the chain outward: fetch jobs from many
portals, enrich a candidate's record from the profile links they already list
on their resume, and reduce the cost of applying. An early framing of that
extension had Rezumi store users' portal passwords, create accounts on their
behalf, and submit applications autonomously.

Three forces constrain the design:

1. **The truth-lock invariant.** Anything Rezumi learns about a person must
   become evidence with machine-checkable provenance, never prose that merely
   looks factual. A score must be explainable and must never be presented as an
   employer or applicant-tracking-system judgement.
2. **Third-party platform terms and candidate safety.** LinkedIn and Naukri
   prohibit automated collection and actively enforce it. Workday, Greenhouse,
   Lever, Ashby, SmartRecruiters, and Workable publish job-board APIs that are
   explicitly intended for consumption. Holding a user's portal passwords would
   make Rezumi a high-value credential-breach target and would require
   defeating bot detection to be useful.
3. **No new architectural path without an ADR.** The repository forbids
   competing frameworks, generic dumping grounds, and scaffolding for phases
   that have no real content.

## Decision

### 1. The authenticated home is activation-first

`/dashboard` gates on the account's own persisted state. When the account has
no document **and** no experience, the home renders a single focused activation
panel instead of zero-valued metrics: what the platform will do, the four-step
chain it will run, one primary upload action, and an explicit manual-entry
path. An account that built a career record by hand is never gated.

Once a document exists, the home renders a deterministic **activation chain**
derived from real state across modules — document scanned, parsed fields
reviewed, career record imported, health report available, first opportunity
compared. The chain reads existing read-only endpoints and links to the owning
module for each decision. It is a projection, not a new orchestration engine,
and it never advances a step on the user's behalf.

### 2. Declared-link evidence enrichment (Phase 11)

Rezumi will read the profile links a user has themselves declared — competitive
programming profiles, code hosts, package registries, publication pages,
personal sites — and turn public achievements found there into **evidence with
provenance and attribution**, so a record reflects what a candidate has
actually done rather than only what they remembered to write down.

Binding rules:

- Only URLs the user declared are fetched. Rezumi does not discover, guess, or
  expand to adjacent profiles, and does not fetch anything behind a login.
- Every fetch reuses the existing hostile-URL controls: HTTP(S) only, every
  resolved address and redirect validated, private/link-local/loopback
  destinations blocked, time and response size capped, content sanitized, no
  remote script execution.
- Each connector sits behind a named `DeclaredProfileConnector` port with a
  deterministic local fake, so local development and tests need no third-party
  credentials or network access.
- Extraction produces a proposal carrying the source URL, fetch timestamp, and
  the exact excerpt it relied on. The user confirms before it becomes citable.
- A fetched public achievement is `Supported` on ingest and `Confirmed` only by
  the user. It never becomes `Verified`: no `VerificationAuthority` provider is
  configured, and a public page is not an authority.
- Any platform whose terms prohibit automated collection is out of scope for
  this connector set regardless of the user declaring the link.

### 3. Job ingestion through published interfaces (Phase 12)

Opportunity supply is built on a `JobSourceConnector` port with adapters for
published ATS and job-board APIs (Greenhouse, Lever, Ashby, SmartRecruiters,
Workable), Workday tenant career-site endpoints, employer-authorized feeds, and
the existing single-URL import. Coverage beyond that is widened by licensing
job data from a provider that carries its own collection rights, not by
collecting it ourselves.

Rezumi does not scrape platforms that prohibit automated collection.

### 4. Assisted apply with an autofill pack, not autonomous submission (Phase 12)

Applying is reduced to near one click without impersonation:

- An **Application Profile** stores the reusable answers portals ask for — work
  authorization, notice period, compensation expectation, locations, links,
  and optional voluntary-disclosure preferences — owner-scoped like every other
  user row.
- For a chosen opportunity, Rezumi assembles a tailored resume version and
  pre-answers the standard questions from the career record, with provenance for
  every factual answer.
- Handoff is a deep link the user opens and submits in their own browser
  session, alongside a copy-ready pack for fields a link cannot prefill.

Rezumi will **not** store third-party portal passwords, create accounts on a
user's behalf, authenticate as a user to a third party, or bypass bot detection
or CAPTCHAs. Where a portal offers OAuth or an employer has enabled a
documented application API, submission may become programmatic under that
mechanism; absent that, the user submits.

### 5. Skill gaps close through existing modules (Phase 13)

Gap-to-learning reuses `role_readiness` competency results as the gap source
and `career_growth` development items as the plan, linked to the evidence a
completed item produces. No new bounded context is introduced, and no learning
recommendation asserts an outcome, ranking, or hiring probability.

### 6. Rezumi Corp ID is a scoped membership identifier

Each account carries a stable Corp ID rendered from its existing account
identifier, with a tier driven only by checks Rezumi actually performs:
confirmed email, a reviewed parsed resume, and confirmed evidence. Copy states
exactly what the identifier attests.

It is not an employer credential, a background check, a third-party identity
verification, or a hiring signal, and it must never be presented as one.
Persisting a dedicated immutable column and any external-facing lookup are
deferred until the phase that needs them; today the identifier is derived, so
it is stable without a migration.

### 7. Navigation consolidates to seven destinations

The sidebar collapses from fifteen entries to Home, Career Record, Resume
Studio, Opportunities, Applications, Prepare, and Growth. Sibling tools move
into per-section sub-navigation rendered inside the section. Every existing
route keeps working; consolidation is a navigation change, not a routing
rewrite, which also leaves room for later phases without regrowing the sidebar.

## Consequences

### Positive

- A new account sees one obvious action instead of a wall of zeros, and the
  workspace visibly progresses as the chain completes.
- Enrichment makes scores fairer in the direction Product intended: a record is
  built from what a candidate demonstrably did, with the source attached.
- Job supply rests on interfaces that are published for this purpose, so
  ingestion is legible, cacheable, and does not depend on evading a defence.
- Rezumi never holds third-party credentials, which removes an entire breach
  class and keeps account creation with the person who owns the account.
- Gap closure and job ingestion add capability without adding bounded contexts.

### Negative

- Assisted apply is one click plus a submit, not zero clicks. Users who expected
  fully autonomous application will experience this as a limitation.
- Published-API ingestion under-covers markets dominated by portals that
  prohibit collection, until licensed data is added.
- The activation chain reads several modules' endpoints, so the home has more
  upstream dependencies and must degrade per section.
- A derived Corp ID cannot yet be looked up externally or survive a future
  identifier change.

### Risks

- **Enrichment misattribution.** A declared link may not belong to the user, or
  a page may be ambiguous. Mitigated by user confirmation before any fetched
  claim becomes citable, and by storing the excerpt relied upon.
- **Corp ID misreading.** A badge can imply more than it attests. Mitigated by
  tier copy naming the specific checks and an explicit disclaimer.
- **Connector drift.** Published endpoints change without notice. Mitigated by
  port isolation, recorded fixtures, and treating every response as hostile.
- **Scope pressure.** Phases 11–13 are large. Mitigated by shipping the
  activation experience first, which is the part that makes the existing
  investment legible.

## Alternatives considered

- **Store portal credentials and apply autonomously.** Rejected. It violates
  the terms of the platforms involved, requires defeating bot detection to
  work, makes Rezumi a credential-breach target, and shifts accountability for
  submissions away from the candidate. Assisted apply captures most of the time
  saving with none of that.
- **Scrape LinkedIn and Naukri for job supply.** Rejected. Both prohibit
  automated collection and enforce it; a product's core supply cannot rest on a
  defence-evasion arms race. Published APIs plus licensed data give a durable
  base.
- **Discover a candidate's profiles automatically.** Rejected. Fetching only
  declared links keeps enrichment consented and auditable; automatic discovery
  would compile a profile the user never authorised.
- **Auto-accept import proposals so the record populates with no review.**
  Rejected. It would violate the invariant that no material career-record
  change is applied silently. The chain instead makes the pending decision
  impossible to miss.
- **A new orchestration module owning the activation chain.** Rejected as
  premature. The chain is a read-only projection over module state; a bounded
  context would duplicate rules that already live in their owning modules.
- **Persist the Corp ID column now.** Deferred. It is the right end state, but
  the migration and ownership rules cannot be integration-tested until the
  local stack is available, and a derived identifier is stable in the interim.
