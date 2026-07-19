# CareerOS security threat model

Status: Phase 7 Resume Builder and verified export controls implemented and locally verified
Method: asset/trust-boundary analysis with STRIDE-style threat enumeration  
Last reviewed: 2026-07-19

## Scope and current posture

This model covers the browser, Next.js application, FastAPI API, Celery workers,
PostgreSQL/pgvector, Redis, S3-compatible object storage, external providers,
administration, CI/CD, and operational telemetry.

Phase 1 accepts authentication, limited account/profile data, session metadata,
consent events, and onboarding progress. Phase 2 also accepts PDF/DOCX resumes,
stores private originals and derived text/reading-order artifacts, and persists
canonical snapshots, processing jobs, Resume Health analyses, findings, and safe
audit events. Phase 3 adds owned career facts, resume-import proposals, evidence
and provenance, private PDF/DOCX evidence attachments, conflicts, achievement
drafts, reminder preferences, immutable evidence history, and redacted Career
Record audit. Phase 4 adds role taxonomy, saved roles, owner-scoped readiness
analyses, evidence-linked competency results, idempotency records, and redacted
Role Explorer audit. Phase 5 adds owned job postings, constrained job-URL
imports, source-spanned requirement extraction, evidence-linked match analyses,
opportunity priorities, idempotency records, and redacted Job Match audit. Phase
6 adds Change Studio change sets, claim-ledger rows, clarifying questions,
immutable output versions, provider-run metadata, idempotency records, and
redacted Change Studio audit. Phase 7 adds structured resumes, immutable resume
versions, private exported objects, round-trip verification reports, short-lived
download intents, idempotency records, and redacted Resume Builder audit. Their
implemented controls are called out below. The product still does not fetch
evidence URLs, bill, or perform administrator actions; controls described for
those later paths remain target requirements, not implementation claims. The
deterministic local AI provider is implemented for development/tests, while
production remote-provider enablement remains a deployment and security review
decision. The fictional dashboard preview remains isolated at `/demo/dashboard`
and does not use authenticated account state.

## Security objectives

1. A person can access only data and operations authorized for their user and
   current tenant.
2. Career documents, evidence, contacts, and account data remain confidential and
   purpose-limited across storage, telemetry, providers, support, and backups.
3. Provenance, evidence state, score inputs, resume versions, consent, and audit
   records retain integrity and explainability.
4. Hostile documents, URLs, and text cannot execute, pivot into internal services,
   exhaust unbounded resources, or change system/model policy.
5. The product remains available under abusive authentication, upload, analysis,
   AI-cost, and queue patterns with controlled degradation.
6. Users retain meaningful review, export, deletion, and session control.

## Assets and classification

| Class                        | Examples                                                                                                                  | Handling baseline                                                                                    |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Restricted authentication    | Password hashes, session/refresh/reset/verification tokens, OAuth secrets, signed URL credentials                         | Never log; hash tokens at rest; managed secrets; narrow access; rotate/revoke                        |
| Restricted career content    | Raw resumes, evidence documents, performance excerpts, application answers, contact details, job notes, interview stories | Private encryption; ownership scope; no analytics payload; provider minimization; retention/deletion |
| Confidential structured data | Parsed profile, evidence graph, scores/features, applications, contacts, model inputs/outputs                             | Ownership and purpose checks; encrypted transport/storage; audited sensitive access                  |
| Security/audit data          | Consent, audit events, access history, hashes, redacted errors                                                            | Integrity/retention controls; no raw document content; limited admin access                          |
| Internal operational data    | Queue/job state, traces, cost/usage, feature flags                                                                        | Redacted IDs; least privilege; bounded retention                                                     |
| Public                       | Marketing content, published policies, public role taxonomy                                                               | Integrity and release review; no user-specific values                                                |
| Fictional demo               | Seeded preview profile and metrics                                                                                        | Explicitly labeled; isolated from production accounts and analytics                                  |

Embeddings inherit the classification of their source. They are not anonymous and
must be deleted, exported, and access-controlled with the source record.

## Actors

- Legitimate guest, individual user, organization member, coach, and administrator.
- Curious or malicious authenticated user attempting cross-user access.
- Unauthenticated attacker, credential stuffer, bot, and cost/availability abuser.
- Malicious file/job author embedding exploits or prompt instructions.
- Compromised or over-privileged provider, administrator, dependency, CI runner,
  support operator, or deployment credential.
- Accidental insider making an unsafe query, log, export, or configuration change.

## Trust boundaries

```mermaid
flowchart LR
    I[Internet / hostile input] --> E[Web and API edge]
    E --> S[Authenticated service boundary]
    S --> D[(Private data services)]
    S --> Q[Queue boundary]
    Q --> W[Restricted worker sandbox]
    W --> D
    S -. minimized requests .-> P[Third-party providers]
    W -. minimized requests .-> P
    C[CI/CD and administrators] --> S
    C --> D
    S --> L[Redacted telemetry]
    W --> L
```

Each arrow is authenticated, encrypted outside a local-only network, least-
privilege, bounded, and observable. Local Compose connectivity is not evidence of
a safe production network policy.

## Security invariants

- A resource ID, object key, queue message, signed URL, role claim, or hidden UI
  control is never sufficient authorization.
- Every user-owned operation applies authenticated subject plus tenant/owner
  scope at the database/service boundary.
- Raw untrusted content is data, never executable instructions.
- Unsupported or ungrounded model output cannot become an accepted claim.
- Objects are private and randomized; original and exported documents are
  immutable, hashed, and linked to exact versions.
- Secrets, raw documents, and tokens never enter logs or analytics by default.
- Required security provider failure is explicit and fails closed or quarantines;
  it never silently becomes a no-op.
- Administrative access does not imply blanket access to raw career content.

## Threat and control register

| ID   | Threat / abuse case                                                    | Primary controls                                                                                                                                                                                                                   | Verification                                                                                                                        | Residual risk / owner                                                                                        |
| ---- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| T01  | Broken access control / IDOR by changing UUID                          | Ownership-scoped repository methods; tenant context; deny-by-default policies; task/object recheck; cross-user audit                                                                                                               | API integration and signed-object tests change IDs/tenant headers                                                                   | Policy/query omissions remain possible; every data phase                                                     |
| T02  | Tenant-isolation failure through joins, search, analytics, or pgvector | Ownership columns/indexes; scoped joins/vector filters; aggregation thresholds; no client-selected unrestricted tenant                                                                                                             | Static query review, adversarial multi-tenant fixtures, property tests                                                              | Future org delegation complexity; Phases 1–10                                                                |
| T03  | Public/signed object leakage or key guessing                           | Private buckets; randomized tenant-scoped keys; short-lived operation-specific URLs; content disposition; authorization before issue/finalize                                                                                      | Signed-PUT binding, owner-scoped finalize/resource denial, destination-origin rejection, and anonymous bucket HTTP 403              | URL forwarding within short TTL; Phase 2                                                                     |
| T04  | File polyglot, wrong extension, malformed parser exploit               | Signature and MIME allowlist; parser isolation; patched libraries; safe failure; original quarantine                                                                                                                               | Malformed/polyglot/wrong-extension corpus                                                                                           | Unknown parser zero-days; sandbox and rapid patching; Phase 2                                                |
| T05  | Malware or macro-enabled document                                      | Malware scan before parsing; reject/quarantine macro formats; never invoke office macros/content                                                                                                                                   | EICAR and macro fixtures in isolated test environment                                                                               | Scanner evasion; layered isolation; Phase 2                                                                  |
| T06  | Zip/decompression bomb or huge document                                | Compressed/uncompressed byte, entry, ratio, page, CPU, memory, and wall-clock limits; streaming; kill worker                                                                                                                       | Signature, malformed/encrypted/polyglot, macro/traversal, expansion entry/ratio, PDF-page, character, timeout, and image-only cases | Resource exhaustion below thresholds; tune/load test                                                         |
| T07  | Path traversal / unsafe temporary filenames                            | Server-generated keys/names; ignore archive paths; canonical temp root; no user path joins; cleanup finally/timeout                                                                                                                | Traversal and symlink fixture tests                                                                                                 | Library-level extraction behavior; Phase 2                                                                   |
| T08  | Uploaded content executes or reaches network                           | No execution; restricted UID/filesystem/capabilities; no unnecessary egress; CPU/memory/time caps; disposable workdir                                                                                                              | Compose policy inspection and restricted worker runtime checks                                                                      | Local Compose is less isolated; production gate Phase 10                                                     |
| T09  | SSRF through job URL, redirects, DNS rebinding, alternate IP forms     | HTTP(S) only; normalized URL; resolve and validate every connection/redirect; block loopback/private/link-local/metadata/reserved IPv4/IPv6; target pinned connection or proxy with egress allow policy; time/byte/redirect limits | IPv4/IPv6/decimal DNS-rebind/redirect/metadata test server                                                                          | Phase 5 validates before each request/redirect but does not yet socket-pin the connection; sanitize/minimize |
| T10  | Remote script/content injection from job import                        | Fetch raw response without browser execution; content-type allowlist; sanitize; store text/source safely; CSP and output encoding                                                                                                  | Script/event-handler/SVG/HTML fixtures                                                                                              | Sanitizer bypass; plain-text default                                                                         |
| T11  | SQL injection or unsafe dynamic filters                                | SQLAlchemy parameters; allowlisted sort/filter fields; no model output in SQL; least-privilege DB role                                                                                                                             | Injection API tests and code scanning                                                                                               | Unsafe future raw SQL; review gate                                                                           |
| T12  | Stored/reflected/DOM XSS or model-output injection                     | React escaping; HTML sanitizer only where rich text required; CSP; safe links; no dangerous HTML; validate model output                                                                                                            | XSS corpus, component/e2e CSP tests                                                                                                 | Rich editor/preview surface; Phases 6–7                                                                      |
| T13  | CSRF on cookie-authenticated mutation                                  | SameSite cookies, CSRF token/origin checks, safe method semantics, CORS allowlist                                                                                                                                                  | Cross-origin mutation tests                                                                                                         | Browser behavior/config drift; Phase 1                                                                       |
| T14  | Credential stuffing, enumeration, brute force                          | Generic responses; IP/account/device-aware limits; progressive delay; breached-password policy where lawful; email verification; monitoring                                                                                        | Abuse/load tests; response equivalence                                                                                              | Distributed botnets and user reuse; Phase 1                                                                  |
| T15  | Session theft/replay/fixation                                          | Secure HTTP-only scoped cookies; rotate hashed refresh/session secrets; invalidate on logout/reset/delete; short lifetimes; session UI; OAuth state/PKCE                                                                           | Replay, rotation, fixation, logout-all tests                                                                                        | Compromised endpoint/browser; optional MFA later                                                             |
| T16  | Password/reset/token compromise                                        | Argon2id calibrated parameters; strong random one-time hashed tokens; expiry/rate limits; no token logging; email-link origin allowlist                                                                                            | Hash configuration and reuse/expiry tests                                                                                           | Email-account compromise; Phase 1                                                                            |
| T17  | Rate-limit bypass or costly endpoint abuse                             | Limits at edge and application keyed by IP/account/tenant/device; normalized identity; quotas, concurrency and body caps; backpressure                                                                                             | Header/IP variants, distributed/concurrency/load tests                                                                              | Proxy attribution errors; tune with telemetry                                                                |
| T18  | Prompt injection in resume, evidence, or job                           | Treat content as quoted untrusted data; separate system policy; strip/flag unsafe control chars; least-data prompts; no tools by default                                                                                           | Adversarial golden fixtures and policy regression                                                                                   | Novel semantic injections; deterministic verifier is final gate                                              |
| T19  | AI fabricates/changes factual claim                                    | Strict schema; evidence IDs and claim ledger; deterministic entity/number/technology/credential checks; reject/question; explicit user review                                                                                      | Unsupported claim, changed ownership/date, metric grounding tests                                                                   | Paraphrase meaning detection; high-risk confirmation                                                         |
| T20  | Malformed or malicious model output reaches shell/SQL/HTML/path        | Parse/validate strict JSON; bounded strings/enums; output encoding; never execute or directly interpolate                                                                                                                          | Schema fuzz and sink-specific tests                                                                                                 | Downstream library bug; keep privilege minimal                                                               |
| T21  | Sensitive data leaks to AI provider                                    | Field/purpose minimization, configurable redaction, consent, no provider training by default, approved regions/retention, DPA, provider disable switch                                                                             | Payload snapshot/privacy tests                                                                                                      | Provider/legal changes; Phase 6 review                                                                       |
| T22  | Sensitive data leaks through logs, traces, errors, analytics           | Central redaction, allowlisted fields, route templates not raw URLs, safe IDs, payload-free events, production error masking                                                                                                       | Secret/PII canary tests and log review                                                                                              | Free-form exceptions; structured logging only                                                                |
| T23  | Excessive AI or render cost                                            | Per-user/tenant/plan quota, idempotency, max tokens/pages, concurrency, timeouts, circuit breaker, cost accounting and alerts                                                                                                      | Retry/idempotency/budget tests                                                                                                      | Provider price/usage spikes; configurable kill switch                                                        |
| T23a | Export file looks correct but drops, duplicates, or reorders facts     | Immutable version pinning, deterministic templates, searchable output, PDF/DOCX reparse, critical mismatch blocking, hash storage, no download intent for blocked exports                                                          | Renderer round-trip, blocked-export download denial, cross-user download, and Playwright export workflow tests                      | Complex font/layout behavior; constrained templates until broader renderer corpus passes                     |
| T24  | Queue replay, forged job, duplicate side effect                        | Authenticated private broker; durable job record; ownership/state/idempotency check; payload references not raw secrets; bounded retry/dead letter                                                                                 | Duplicate/reordered/forged payload tests                                                                                            | Redis local durability differs from production; deployment ADR                                               |
| T25  | Dependency or build compromise                                         | Lockfiles/hashes, least-privilege CI, pinned actions/images, review of updates, SCA/container/secret scanning, provenance and SBOM objective                                                                                       | CI security jobs and reproducible build                                                                                             | Registry/upstream compromise; ongoing                                                                        |
| T26  | Secret committed or exposed in image/client                            | `.env.example` placeholders; secret scanning; server-only vars; build/image inspection; managed secret injection                                                                                                                   | Git/image/bundle secret scans                                                                                                       | Human error or CI artifact leakage                                                                           |
| T27  | Admin abuse or support overreach                                       | Separate role/permissions, just-in-time purpose-bound access, no raw default, re-auth/MFA target, immutable audit, alerts, dual control for destructive actions                                                                    | Permission matrix and audit tests                                                                                                   | Authorized insider misuse; governance and monitoring                                                         |
| T28  | Audit tampering or missing evidence                                    | Append-oriented audit store, server-generated actor/request/time, restricted mutation, retention/export controls, coverage tests                                                                                                   | Critical-action audit assertions                                                                                                    | DB superuser compromise; external/WORM export later                                                          |
| T29  | Data remains after deletion or appears in backup/vector/cache          | Data inventory and erasure orchestration; tombstones; object/vector/cache/provider deletion; backup expiry policy; status to user                                                                                                  | End-to-end deletion and restore-window tests                                                                                        | Immutable backup retention; disclose and minimize                                                            |
| T30  | Billing webhook replay/forgery                                         | Signature/timestamp verification, raw-body validation, event idempotency, state-machine constraints, amount/plan lookup server-side                                                                                                | Replay/order/signature tests                                                                                                        | Provider account compromise; Phase 10                                                                        |
| T31  | Denial of service against API, DB, queue, object store                 | Body/query bounds, timeouts, pools, backpressure, per-tenant concurrency, queue isolation, autoscaling and graceful degradation                                                                                                    | Load/soak/failure tests                                                                                                             | Large distributed attack; upstream protection                                                                |
| T32  | Sensitive health/readiness metadata disclosure                         | Minimal status/version; no credentials, stack traces, hostnames, bucket names, or raw dependency errors; admin detail separately protected                                                                                         | Response snapshot tests                                                                                                             | Version fingerprinting; patch promptly                                                                       |
| T33  | Cache key collision or cross-tenant result reuse                       | Namespace by environment/version/tenant/user/resource; cache only authorized representations; short TTL/invalidation                                                                                                               | Cross-tenant cache tests                                                                                                            | Future caching complexity; introduce only with tests                                                         |
| T34  | OAuth account-link takeover                                            | State, nonce, PKCE, exact redirect allowlist, verified provider identity, explicit authenticated link/unlink, conflict handling                                                                                                    | Login/link CSRF and provider-account collision tests                                                                                | Compromised provider identity; Phase 1                                                                       |
| T35  | Insecure deletion/reset/retry operation                                | Re-auth for sensitive actions, confirmation, ownership, idempotency, audit, safe allowlisted retry states                                                                                                                          | Cross-user/replay/unsafe retry tests                                                                                                | Social engineering; clear UX and notices                                                                     |

## File-processing security design

### Admission

The API issues a single-purpose, short-lived upload intent only after rate,
quota, and account-or-guest ownership checks. It records expected media/size and
a randomized private staging key. The browser accepts only the configured object
origin and receives a method/headers-constrained signed `PUT`, never permanent
credentials. Finalization treats browser/object metadata as assertions, not
proof: it checks owner, intent expiry, exact stored byte count, stored media type,
and a bounded byte signature before promoting the object into quarantine.

The browser keeps intent/transfer/finalize retry state only in memory and can
reuse it after an ambiguous response while the page stays mounted. It never puts
signed URLs or capability material in durable browser storage. The tradeoff is
that a lost upload-intent response or page reload may reserve intake quota until
the default five-minute TTL expires; scheduled cleanup later removes orphaned
staging bytes. Phase 2 uses one signed `PUT`; there is no resumable or multipart
transfer.

Initial accepted types are PDF and DOCX. Macro-enabled Office formats, archives,
executables, encrypted documents that cannot be inspected, and unsupported types
are rejected with a safe user-facing reason. Limits are configuration with secure
upper bounds, not user-controlled values.

### Quarantine and processing

New objects remain quarantined. A restricted worker downloads the bounded object
into a fresh randomized child of a private `noexec` tmpfs, runs required ClamAV,
then applies PDF/DOCX signature, expansion, entry, compression-ratio, character,
artifact, and wall-clock limits plus an authoritative PDF page cap before
extraction. It runs as a non-root user
with a read-only base filesystem, dropped capabilities, `no-new-privileges`,
bounded CPU/memory/PIDs, and no edge network. It never executes embedded scripts,
macros, links, or attachments.

The temporary directory context removes bytes on success or exception. An
infected document is rejected. Scanner connection/protocol failure is retryable
only within the bounded job policy; the object remains quarantined and an
exhausted job is rejected/dead-lettered rather than parsed unchecked. Malformed,
encrypted, polyglot, macro-bearing, traversal, expansion-bomb, PDF-page-limit, and
timeout inputs produce allowlisted safe error codes. Raw parser/scanner output is
not returned or logged.

The local `python-docx` path cannot reliably derive rendered DOCX page count. It
therefore bounds DOCX by upload bytes, archive entries, expanded bytes/ratio,
extracted characters/blocks, artifact size, CPU/memory, and wall clock. A future
layout-aware rendering provider is required before claiming DOCX page-count
enforcement.

Each worker delivery receives a fresh fencing token stored only as its SHA-256
digest and a durable lease longer than the Celery hard timeout. A concurrent
delivery performs a delayed busy retry rather than sharing the lease. An expired
lease can be reclaimed within the durable attempt cap, and every progress/result
write verifies the current token so a stale worker cannot commit after recovery.
A scheduled database-only reconciler recovers stale published, retryable-failed,
and expired-running jobs through a fresh outbox generation; it first clears an
expired lease/token and refuses to exceed either processing or recovery budgets.

### Storage and lifecycle

Original quarantine objects are immutable by application policy; the local
bucket denies anonymous access. Plain-text and reading-order derivatives use
separate randomized keys and ownership checks. Content hashes support integrity,
but there is no cross-user deduplication or existence signal. Local bucket
versioning is not presented as the production retention control.

Guest access uses a high-entropy opaque capability stored only as a keyed hash on
the server and delivered in a path-restricted `HttpOnly`, `SameSite=Lax` cookie.
A separate double-submit token and exact-origin check protect guest mutation. One
guest capability permits one active intake; both capability and document default
to 24-hour retention. Expiry first queues the same durable deletion job used by
explicit delete, then revokes the capability. Account conversion requires a
valid account session, account CSRF, valid guest capability, explicit consent,
and account quota; it also requires a ready document, completed analysis, and no
active/retryable job. It copies objects to new randomized account keys and
transfers retained content/job history before deleting guest-key copies. Existing
guest audit records remain append-only under the original guest scope.

Deletion removes the original and derivative objects, purges canonical snapshots,
analyses, feature values/contributions, findings, and components, and leaves only
a redacted document/job/audit record. Object promotion/claim compensation and
rejected/expired staging or orphan quarantine cleanup use owner-scoped durable
cleanup rows with bounded backoff/attempts and terminal dead-letter state.
Explicit deletion is a fenced durable job with bounded retry/dead-letter and a
staging cleanup backstop. The transactional job outbox uses the same bounded
operational principle for broker publication. Backup expiry, account-wide export/deletion,
embeddings, OCR artifacts, and provider erasure remain later-phase production
policy because those stores are not part of Phase 2.

### Resume export storage and verification

Phase 7 exported resume files use separate randomized private object keys scoped
by owner and immutable version. API responses expose the export ID, status,
format, size, hash, and verification report, never the internal object key.
Download URLs are produced only through short-lived owner-checked download
intents and are unavailable for failed, deleted, or verification-blocked exports.

Rendering input is an immutable structured resume version whose bullets carry
eligible evidence IDs. Server validation rejects unsupported edits before render.
Generated PDF/DOCX bytes are parsed again by the document extractor; critical
missing bullets, duplicate bullet text, unreadable output, ordering failures, or
grounding mismatches block the export. Text and JSON exports still receive a
structured verification report and hash, but do not require binary reparse.

Export deletion rechecks ownership, removes the private object, marks the export
deleted, and leaves redacted audit/status metadata. Verification failures and
render errors store safe codes/messages only; logs must not include resume text,
download URLs, object keys, or rendered bytes.

## URL-import security design

The server, never the user's browser session, performs a constrained fetch. URL
normalization rejects credentials, fragments where irrelevant, unsupported
schemes, ambiguous hosts, and malformed encodings. Resolution validates all
addresses before each request and redirect. IPv4-mapped IPv6 and alternate
address representations are normalized before network-range decisions.

The fetcher caps DNS/connect/read/total time, redirects, decompressed bytes, and
content type. It does not send user cookies or internal credentials and does not
execute JavaScript. Phase 5's local importer relies on the HTTP client's normal
TLS hostname verification but does not yet pin the TCP socket to the prevalidated
address, so DNS rebinding between validation and connection remains a documented
production hardening item. A production egress proxy/firewall blocks metadata and
private networks even if application validation fails.

## AI and grounding security design

Documents are surrounded by fixed untrusted-data delimiters and cannot supply
system or tool instructions. Providers receive the minimum required fields and
opaque evidence IDs. Tool use is disabled unless a future reviewed capability
needs a narrow allowlisted tool.

Model output first passes size/JSON/schema validation, then the deterministic
grounding verifier described in `docs/ai-grounding-policy.md`. Unknown evidence
IDs, unsupported facts, unconfirmed numbers, entity/date changes, or changed
contribution semantics are rejected. Rejected output may produce a safe
clarifying question but never an exportable claim.

Prompt/model/provider versions, input evidence IDs, validation outcome, usage,
and cost are recorded without raw prompt logging. The display layer escapes
output and enforces the same content policy after a user's manual edit.

## Authentication and authorization design

Phase 1 uses FastAPI-owned sessions. Passwords use Argon2id with calibrated cost.
Session/refresh secrets are high-entropy, hashed in storage, bound to a session
record, rotated on use, and revoked on logout, password reset, account deletion,
or suspicious reuse. Cookies are Secure and HTTP-only in production with an
appropriate SameSite policy; state-changing requests use CSRF defenses.

OAuth uses exact redirect URIs, state, nonce, and PKCE. Account linking requires
an authenticated session or a verified conflict-resolution flow; provider email
alone is not always sufficient proof.

Each service method receives an authorization context and queries by both owner/
tenant and UUID. Background jobs store owner/tenant and reauthorize durable
resources. Organization roles grant explicit capabilities, not blanket tenant
reads. Admin capabilities are separate and audited.

### Abuse-source attribution boundary

The pre-authentication and Phase 2 guest-intake rate key is deliberately separate
from identity. Local
Compose publishes only `web-edge`; the Next.js container has no host port. The
edge discards `Forwarded`, `X-Forwarded-For`, `X-Real-IP`, and vendor address
headers supplied by the client, then writes the direct socket peer. The
server-only BFF normalizes that value and HMAC-signs it; the API verifies the
signature in constant time and uses only the opaque signature as the pre-auth/
first-guest upload rate subject. Invalid or unavailable signals fail closed in
staging and production. This mechanism grants no session, capability, owner, or
tenant authority.

The local policy is intentionally single-hop. Behind a cloud load balancer, the
edge sees the balancer socket address, so attribution collapses until a
deployment-specific allowlist defines exactly which proxy hop may supply which
address header. Accepting arbitrary forwarded headers would reintroduce spoofing;
distributed actors can still evade any per-source key and require upstream edge
controls plus account/domain quotas.

### Phase 1 implemented controls and evidence

- Passwords are Argon2id hashes. Session, refresh, verification, recovery, OAuth
  state, and PKCE material are high-entropy opaque values; persisted secrets use
  keyed hashes rather than recoverable plaintext.
- Access and refresh cookies are HTTP-only, production-secure, and scoped to the
  required paths. A session-bound readable CSRF cookie plus matching header and
  origin/CORS allowlist protect state changes. The web proxy is same-origin,
  header-allowlisted, redirect-controlled, time-bounded, and cannot select an
  arbitrary upstream.
- Refresh use rotates the token and detects replay; a replay revokes the family.
  Verification and recovery tokens are short-lived and single-use. Successful
  password recovery invalidates sessions.
- Registration, resend, and recovery responses resist account enumeration. Redis
  applies bounded abuse controls. Request bodies are capped at 1 MiB for both
  declared and chunked bodies before application parsing.
- Google OAuth state is browser-bound and one-use. The adapter requires state,
  nonce, PKCE, exact configured redirects, RS256 signatures, audience/client and
  authorized-party checks, plus `at_hash` when supplied. Account collisions fail
  safely and tests use deterministic providers without live credentials.
- Owner-scoped repositories and route dependencies reject anonymous and cross-user
  access. Session, authentication, consent, and security-sensitive changes emit
  redacted audit events; recent-auth hooks exist without claiming MFA support.

Unit/API tests cover these invariants, two integration workflows exercise real
PostgreSQL and Redis, and the isolated browser journey proves registration through
Mailpit verification, login, onboarding, exact-session revocation, logout, and
protected-route denial on desktop and mobile. Exact counts and commands are in
`PLANS.md`.

### Phase 2 implemented controls and verification evidence

- Migration `20260715_0003` gives every upload, document, artifact, canonical
  snapshot, analysis, job, and object cleanup exactly one account or guest owner,
  with foreign keys, state/value checks, scoped indexes, and owner-scoped
  repository methods. Analyses persist feature-schema version, typed feature
  values, and normalized weighted contributions rather than an unauditable total.
- Presigned upload intents use randomized keys and exact expected media/size.
  Finalize repeats ownership and byte admission before staging-to-quarantine
  promotion. MinIO uses a non-root application identity limited to the private
  document bucket and one exact browser CORS origin.
- Required ClamAV scanning, guarded local PDF/DOCX extraction, randomized
  temporary paths, a restricted worker container, bounded job retry/dead letter,
  per-invocation token/lease fencing, delayed busy delivery, and allowlisted queue
  task names reduce hostile-file and queue-forgery blast radius.
- Account access uses the existing session/CSRF principal. Guest access uses a
  separately hashed capability plus guest CSRF/origin policy. Resource UUID alone
  cannot retrieve, correct, analyze, claim, cancel, or delete content.
- Canonical corrections are immutable successors with optimistic concurrency.
  Resume headers are narrowly validated, all-no-op correction is rejected,
  correction/analysis have separate owner-scoped rates, and domain history caps
  bound revision/job growth. Analysis and deletion are idempotent durable jobs;
  scheduled retention uses the same object/content deletion path. Durable object
  cleanup and transactional outbox publication have bounded attempts/backoff and
  dead-letter state. Audit metadata contains safe IDs/state, not filename,
  document text, signed URL, capability, or parser output.
- Focused tests cover cross-owner denial; capability scope/expiry/claim; quota and
  retention; infected and unavailable scanner behavior; wrong-signature,
  malformed, encrypted, polyglot, macro, traversal, expansion, image-only, and
  timeout documents; private S3 and real ClamAV contracts; outbox, cancellation,
  retry/dead letter, fencing/lease recovery, BFF signal/header overwrite,
  route-template payload-free logging; and registered/guest browser workflows.

These controls and the same-revision local container, integration, E2E, and scan
gates pass as recorded in `PLANS.md`; hosted run `29378312134` also passes.

### Phase 3 implemented controls and verification status

- Migration `20260715_0004` gives Career Record rows a non-null owner and uses
  owner-aware uniqueness, foreign keys, checks, and indexes for profile entities,
  nested links, evidence revisions/sources/metrics/conflicts/usage, proposals,
  attachment workflow state, achievements, reminders, and audit events.
  Repositories fetch by owner plus ID; nested links validate both resources in the
  same scope, and cross-user/unknown IDs have indistinguishable not-found behavior.
- Phase 3 is account-only and reuses authenticated server-side sessions, CSRF,
  exact-origin, body limits, safe problem responses, and request/trace context.
  Positive versions and strict quoted `If-Match` values reject stale writes.
  Proposal review, attachment finalize, and achievement conversion prevent replay
  from silently duplicating or overwriting career truth.
- Evidence strength and lifecycle are separate server decisions. Clients cannot
  submit a resulting strength; owner confirmation produces Confirmed only after
  validation. The production service composes no `VerificationAuthority`, so
  neither a client, model, nor owner can manufacture Verified evidence. Material
  edits create immutable Inferred revisions, and open conflicts, unavailable
  provenance, archive/delete lifecycle, Inferred, and Unsupported evidence are
  excluded by the owner-scoped downstream eligibility query.
- Resume provenance crosses the module boundary only through an explicit
  ownership-checking application query. Career Record copies bounded source IDs,
  revision/schema information, source span/digest, and a review excerpt into a
  pending proposal or immutable evidence revision. It does not foreign-key career
  truth to a deletable resume or treat parser confidence as confirmation.
- Evidence attachments accept bounded PDF/DOCX only. Admission and download use
  randomized private object keys and short-lived operation/key/media/size-bound
  signed URLs. Finalize repeats ownership, expiry, object metadata, exact size,
  and byte-signature checks while locking the parent evidence against deletion.
  Required ClamAV and the bounded extractor run in the restricted worker and fail
  closed; attachment presence alone cannot raise evidence strength.
- Attachment jobs persist owner, idempotency, trace, status, attempts, safe error,
  lease, hashed fencing token, and terminal state. Identifier-only outbox payloads,
  bounded publish/process/cleanup retries, dead letters, stale-job reconciliation,
  and durable object cleanup cover broker loss, worker death, and object-store
  failure without logging raw evidence, answers, filenames, signed URLs, or bytes.
- Focused domain, repository, API, worker, provider, component, and browser tests
  cover the controls above. The desktop primary journey creates career data,
  confirms evidence, and explicitly converts an achievement; it does not exercise
  a mobile end-to-end career journey or independent verification. The final
  local `scripts/verify-phase3.ps1` result and hosted Phase 3 CI pass as recorded
  in `PLANS.md`.

### Phase 4 implemented controls and verification status

- Public role taxonomy rows carry source, license, version, and published time.
  User-owned saved roles, readiness analyses, components, competency results,
  evidence links, idempotency rows, and audit events carry non-null owner scope
  and supporting indexes/constraints.
- All routes require authenticated account sessions. Mutations require CSRF and
  exact-origin protection; saved-role updates/deletes require strict `If-Match`;
  analysis requires bounded idempotency keys. Cross-user saved-role and analysis
  reads return not-found rather than exposing resource existence.
- Readiness consumes only the Career Record application snapshot. It does not
  query evidence tables, accept client evidence IDs as proof, copy raw evidence
  text into analysis/audit rows, or treat a listed skill as demonstrated without
  eligible matching evidence.
- Scoring is deterministic fixed-point code with persisted engine/configuration/
  feature-schema versions, feature hash, input snapshot, components, and
  competency results. Responses include the internal-score disclaimer and never
  label readiness as an ATS score, hiring probability, or guarantee.
- Unit, migration-shape, API, repository integration, web component, and
  Playwright workflow coverage exercise owner scope, idempotency, stale versions,
  no-signal behavior, evidence relevance, comparison, and disclaimer display.
- The consolidated local `scripts/verify-phase4.ps1` gate passed on 2026-07-19,
  including real dependency integrations, migration rollback/forward repair,
  worker hardening probes, and the isolated Role Explorer browser journey.

### Phase 5 implemented controls and verification status

- Migration `20260719_0006` adds owner-scoped job postings, current extracted
  requirements, immutable match analyses, requirement match rows, evidence-link
  snapshots, opportunity priorities, idempotency records, and redacted audit
  events with constraints, foreign keys, and scoped indexes.
- All routes require authenticated account sessions. Mutations require CSRF;
  create/import/analyze/priority operations require bounded idempotency keys; and
  job update/delete require strict `If-Match`. Cross-user job, analysis, and
  priority reads return safe not-found responses.
- Job Match consumes eligible evidence only through the Career Record application
  snapshot and role context only through the Role Readiness application service.
  It does not accept client evidence IDs as proof and does not query Phase 3 or
  Phase 4 tables directly.
- URL import accepts HTTP(S) only, rejects credentials and non-public resolved
  addresses, repeats validation for redirects, caps redirects/time/bytes, avoids
  cookies/scripts/browser execution, and sanitizes HTML to plain text. The
  remaining socket-pinning hardening item is documented above and in ADR 0011.
- Application Readiness and Opportunity Priority are deterministic, versioned,
  evidence-linked internal measurements. Responses include the canonical
  disclaimer and never describe the result as an employer score, ATS score,
  hiring probability, or guarantee.
- Unit, provider, migration-shape, API, repository integration, web component,
  and Playwright workflow coverage exercise owner scope, idempotency, stale
  versions, source spans, sanitizer/SSRF rejection, injected job text, hard gaps,
  matrix display, and disclaimer visibility. Final consolidated local Phase 5
  verification is recorded in `PLANS.md`.

### Phase 6 implemented controls and verification status

- Migration `20260719_0007` adds owner-scoped change sets, operations,
  claim-ledger rows, clarifying questions, immutable versions, provider runs,
  idempotency records, and redacted audit events with scoped indexes and
  constraints.
- Change Studio consumes Career Record evidence and Job Match requirements only
  through application services. It reauthorizes by owner and never trusts a
  client-provided evidence or requirement ID as proof.
- All reads require authenticated account sessions. Mutations require CSRF,
  bounded idempotency keys, and current `If-Match` versions where an existing
  change set is modified. Cross-user change sets and clarifications return safe
  not-found responses.
- Provider output is treated as hostile JSON. Strict parsing rejects unknown
  fields and invalid IDs/enums/ranges; deterministic grounding blocks unsafe sink
  content, prompt-injection text, unsupported facts, unauthorized evidence,
  ungrounded numbers, ownership/leadership inflation, and causation claims not
  supported by evidence.
- The deterministic local provider only reuses eligible evidence text already
  linked to saved job requirements. The HTTP JSON provider is HTTPS-only,
  credential-required, timeout/retry/response-size bounded, and protected by a
  circuit breaker; production rejects deterministic provider configuration.
- Accept/edit/alternative/lock/reject/undo/redo/restore/answer actions are
  explicit user decisions, append audit records, and preserve immutable output
  versions. Clarification answers do not become eligible evidence by themselves.
- Unit, adversarial grounding/provider, migration-shape, API, repository
  integration, web component, and Playwright workflow coverage exercise owner
  scope, idempotency, stale versions, malformed provider output, unsupported
  claims, numeric eligibility, provenance display, and the primary review flow.
  Final consolidated local Phase 6 verification is recorded in `PLANS.md`.

## Privacy, retention, and consent

- Default: user content is not used to train models.
- Record consent purpose, policy version, timestamp, and revocation.
- Minimize data sent to providers and negotiate retention/data-use terms before
  enabling a production provider.
- Define lifecycle by class: unfinalized upload, guest document, active account,
  archived evidence, audit/security log, deleted account, backup, and billing
  record. Phase 2 defaults upload intents to five minutes and guest capability/
  document retention to 24 hours; Phase 3 evidence-attachment admission defaults
  to ten minutes and download signatures to two minutes. Production account,
  audit, backup, and legal
  durations remain a Phase 10 policy decision; indefinite raw-document retention
  is not an acceptable default.
- Data export includes understandable structured records and files with integrity
  metadata; it excludes other tenants and internal security secrets.
- Erasure is a tracked, idempotent job with per-store status and retry/dead-letter
  handling. Legal retention exceptions are narrow and disclosed.

## Logging and monitoring requirements

Allowlisted structured fields include timestamp, level, service, environment,
route template, status, duration, request/trace ID, opaque actor/tenant/resource
ID, job type/status/retry, provider identifier, token/cost counts, and redacted
error code. Do not record request/response bodies, raw query content, document
text, generated prose, prompt text, object signed URLs, secrets, or tokens.

The implemented HTTP middleware emits only the matched route template (or
`unmatched`), method, status/duration, request/trace context, and exception class.
It never logs the raw path/query, body, headers, exception message, or traceback
at this PII-bearing boundary. Payload-bearing library access/client loggers are
disabled in favor of allowlisted structured application events. Unexpected
exceptions are converted to generic no-store `internal_error` problems at this
boundary instead of being re-raised into the ASGI server traceback logger.

Alert on repeated auth failures/session reuse, authorization denials and ID
enumeration patterns, upload/scanner/parser anomalies, SSRF policy blocks, rate-
limit spikes, queue age/retries/dead letters, AI budget/grounding failures,
administrator sensitive actions, and deletion/retention failures.

## Required security tests by phase

| Phase | Blocking security evidence                                                                                                                                          |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0     | Secret/dependency/container scan foundation; minimal health responses; no real PII in fixtures/logs; Compose services not unintentionally public beyond local needs |
| 1     | Registration/session/reset/OAuth abuse tests; CSRF; rotation/replay; anonymous and cross-user/tenant authorization; audit coverage                                  |
| 2     | Hostile upload corpus; signature/limit/malware/expansion/path/timeout; worker egress/resource policy; object-key and deletion isolation                             |
| 3     | Evidence transition/provenance/ownership; attachment access; unsupported evidence exclusion; conflict audit                                                         |
| 4     | Taxonomy input validation and cross-user saved-role/readiness history isolation                                                                                     |
| 5     | SSRF matrix, sanitizer, source-span integrity, URL limits, hard-gap integrity, prompt-injected job text                                                             |
| 6     | Strict-output fuzzing, unsupported claim/number rejection, prompt injection, cost/idempotency, XSS-safe diff/render, manual-edit revalidation                       |
| 7     | Template injection, renderer sandbox, round-trip grounding/integrity/hash, private export, immutable version/restore                                                |
| 8     | Application/contact/document authorization; consistency checks; stage/action audit; no autonomous submission                                                        |
| 9     | Contact consent, sensitive notes isolation, analytics aggregation/privacy and non-causal language                                                                   |
| 10    | Billing webhook, admin matrix/audit, end-to-end export/deletion, backup restore, load/DoS, penetration test, dependency/container/IaC scan                          |

## Phase 0 security checklist

- [x] `.env.example` contains no real secret and actual `.env` files are ignored.
- [x] Web/API/worker images run without development servers or embedded secrets.
- [x] Health endpoints return minimal safe data; readiness fails on required
      dependency loss without returning credentials or raw stack traces.
- [x] PostgreSQL, Redis, and MinIO use explicit local-only credentials and are not
      presented as production configuration.
- [x] Container services use health checks, bounded restart behavior, and named
      volumes; unnecessary host ports are avoided or documented.
- [x] CI installs from committed lockfiles and runs format/lint/type/test/build plus
      available secret/dependency/container scans.
- [x] Fictional UI fixtures are labeled and contain no real private data.
- [x] `make verify` and Compose health are green in the integrated working tree.

These checks are regression gates; a later failure reopens the affected phase in
`PLANS.md`.

## Incident and recovery expectations

Phase 10 must document owners and playbooks for credential/session compromise,
tenant data exposure, malicious upload/parser exploit, provider data incident,
prompt/grounding bypass, queue/cost runaway, admin abuse, object exposure, and
deletion/backup failure. Immediate capabilities include provider/feature kill
switches, token/session revocation, object quarantine, queue pause, key rotation,
audit preservation, affected-user assessment, and legally appropriate notice.

Backup is not complete until a restore into an isolated environment verifies
integrity, ownership, migrations, object references, and documented RPO/RTO.

## Open decisions and residual risks

- Production region, data residency, account/backup retention durations, RPO/RTO,
  identity email, AI/OCR/parser/scanner/billing providers, queue service, and
  support-access process are not selected. ClamAV and the local PDF/DOCX parser
  are Phase 2/3 local/initial adapters, not a production provider decision.
- No application sandbox fully eliminates parser zero-day risk; isolation,
  patching, corpus testing, and kill switches remain necessary.
- Resume and evidence-attachment parser timeout uses `asyncio.to_thread`;
  cancelling the await does not
  forcibly terminate the underlying Python thread. Celery task limits and the
  non-root, read-only, CPU/memory/PID-bounded, no-edge-network worker constrain
  impact, but killable per-parser subprocess isolation remains production
  hardening work.
- Semantic grounding cannot perfectly detect meaning drift. High-risk claims,
  numbers, leadership, and ownership require stricter deterministic checks and
  user confirmation.
- Distributed abuse can defeat simple rate keys. Edge controls and telemetry must
  complement application quotas.
- The local signed-source chain trusts only the `web-edge` socket peer. A cloud
  load balancer collapses clients to that peer until a deployment-specific
  allowlisted trusted-hop policy is implemented; trusting arbitrary forwarded
  headers is prohibited.
- Upload retry state is in-memory only. A lost intent response or page reload may
  reserve Resume Health quota for up to its default five-minute intent TTL or an
  evidence attachment slot for up to its default ten-minute admission TTL.
  Neither flow has resumable transfer. This is an availability/UX limitation, not
  a reason to persist signed URLs or weaken admission.
- DOCX rendered page count is not authoritative in `python-docx`; byte/archive/
  expansion/character/block/artifact/resource limits apply until a reviewed
  layout-aware rendering provider is introduced.
- MFA is not implemented; recent-auth and session hooks only preserve a future
  integration point. Live Google credentials and production SMTP delivery were
  not part of the local gate, so provider enablement requires a separate
  configuration and contract review.
- Account export/deletion orchestration and final retention periods remain later
  phase work; Phase 1 consent/audit, Phase 2 document deletion, and Phase 3
  evidence/attachment deletion do not substitute for account-wide erasure.
- OCR is an explicit optional port but no Phase 2/3 OCR adapter is enabled.
  Image-only resumes therefore return parser warning/insufficient data, and image
  content in evidence attachments is not promoted into claim text.
- No independent evidence verifier is selected. Verified remains intentionally
  unreachable in production until a reviewed provider and operating process can
  supply method, verifier, scope, source, and time without trusting the claimant.
- External HTTP(S) evidence URLs are stored as untrusted provenance metadata only;
  Career Record does not fetch them. Any future evidence fetch must use or harden
  the Phase 5 redirect/DNS/private-address/size/time SSRF policy rather than
  reusing a generic HTTP client.
- Phase 4 uses a small CareerOS-authored seed role taxonomy. External taxonomy
  provider ingestion, admin curation workflow, localization, and market-specific
  role calibration remain later work.
- Backups and third-party retention delay physical erasure; policy and user
  messaging must describe the bounded window accurately.
- Local Compose is not hardened for hostile multi-user or internet-facing
  use.
- The high-severity image gate has two exact-version exceptions in `.grype.yaml`:
  CPython 3.13.14 `CVE-2026-15308` has no supported 3.13 fix and the current API
  does not parse untrusted HTML; Next.js 16.2.10 vendors undici 6.26.0 affected by
  WebSocket-only `GHSA-vxpw-j846-p89q`, while the product has no WebSocket client
  path.
  A Python base-image or Next.js update must remove the corresponding exception.
- The 2026-07-15 scan also reports medium findings in CPython 3.13.14 whose listed
  fixes are 3.15 prereleases, plus vendored `undici` 6.26.0 and `tar` 7.5.15
  findings below the configured fixable-high gate. Dependency/base-image upgrades
  must remove them when compatible stable releases are available; `pnpm audit`
  and `pip-audit` currently report no known actionable application dependency.

Any new external data flow, public endpoint, file type, AI tool, administrator
capability, authentication method, or tenant-sharing feature requires this model
to be reviewed before release.
