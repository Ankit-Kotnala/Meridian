# Rezumi product requirements

Status: baseline product contract  
Version: 0.2

Last reviewed: 2026-07-25

## Product definition

Rezumi is a career application operating system, not a resume parser or an
“ATS score checker.” It helps a person maintain a durable, structured career
profile and evidence record, then produce and manage truthful, reviewable career
materials and workflows.

**Tagline:** Your career. Verified. Elevated.

### Product outcomes

- Explain general resume health without requiring a job description.
- Make the structured career profile—not a particular resume—the durable source
  of truth.
- Connect important facts, metrics, skills, and claims to provenance and evidence.
- Explain readiness for roles and coverage of exact job requirements without
  pretending to predict hiring.
- Give users granular control over every material suggested change.
- Produce ATS-readable files and verify them by parsing the output again.
- Keep resume, application, networking, and interview claims consistent.
- Help users track applications and continuously capture career achievements.
- Learn from observed outcomes while clearly avoiding causal claims.

### Non-goals for the first production release

- Knowing or reproducing an employer's private ATS score or ranking algorithm.
- Predicting or guaranteeing interviews, offers, compensation, or employment.
- Inventing facts to make a candidate appear stronger.
- Applying material edits or submitting job applications autonomously.
- Scraping private contacts or protected job content without consent.
- Treating an LLM response as an authoritative score, policy decision, database
  command, or rendered document.

## Personas and access modes

| Persona                   | Primary need                                                            | Initial access                                                       |
| ------------------------- | ----------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Guest evaluator           | Learn whether one PDF/DOCX is machine-readable and clear                | Limited, short-lived resume-health report; no durable profile        |
| Individual career builder | Maintain evidence and generate consistent materials over time           | Full user-owned profile and workflows according to plan entitlements |
| Active job seeker         | Compare roles/jobs, tailor documents, track applications and interviews | Job Hunt Sprint or Pro capabilities                                  |
| Coach/organization member | Support multiple consenting users with comments and administration      | Future organization tenancy; never implicit raw-document access      |
| Platform administrator    | Operate health, jobs, taxonomy, templates, plans, flags, and audits     | Separate least-privilege, audited administration                     |

## Non-negotiable product rules

### PR-TRUTH: factual integrity

- **PR-TRUTH-001:** Every generated factual career claim SHALL link to one or
  more eligible evidence records and preserve their provenance.
- **PR-TRUTH-002:** Rezumi SHALL NOT invent employers, dates, titles,
  responsibilities, accomplishments, numbers, savings, customers, team size,
  technologies, certifications, education, awards, leadership, or ownership.
- **PR-TRUTH-003:** Missing facts SHALL yield a clarifying question or a clearly
  marked placeholder that cannot be exported, never a plausible invented fact.
- **PR-TRUTH-004:** Numeric generated claims SHALL map to user-confirmed or
  independently verified metric evidence.
- **PR-TRUTH-005:** Unsupported evidence SHALL not be supplied to generation.
- **PR-TRUTH-006:** Contribution wording SHALL not turn collaboration into sole
  ownership or otherwise change meaning.

### PR-CONTROL: user authority

- **PR-CONTROL-001:** A material suggestion SHALL show original and suggested
  content, reason, evidence, supported job requirement when applicable,
  confidence/risk, and confirmation need.
- **PR-CONTROL-002:** The user SHALL be able to accept, reject, manually edit,
  request another version, undo/redo, and restore an earlier version.
- **PR-CONTROL-003:** Exported/published resume versions SHALL be immutable.
- **PR-CONTROL-004:** “Apply all” SHALL be limited to policy-defined safe changes
  and SHALL NOT bypass confirmation-required changes.

### PR-SCORE: honest measurement

- **PR-SCORE-001:** Scores SHALL be deterministic, configurable, versioned, and
  reproducible from stored structured features.
- **PR-SCORE-002:** An LLM SHALL NOT return the final numerical score.
- **PR-SCORE-003:** Each score SHALL expose components, contributions, evidence,
  missing-data treatment, formula version, and actionable findings.
- **PR-SCORE-004:** Hard requirements SHALL remain separately visible and SHALL
  NOT be hidden inside an average.
- **PR-SCORE-005:** Score and readiness views SHALL display this language where
  misunderstanding is plausible:

  > Rezumi scores are internal readiness measurements. They are not scores
  > provided by an employer or applicant tracking system and do not guarantee
  > interviews or employment outcomes.

- **PR-SCORE-006:** Role readiness SHALL NOT be labeled a hiring probability.
- **PR-SCORE-007:** Outcome analytics SHALL use correlation/pattern language and
  SHALL NOT claim a resume change caused an interview or offer.

## Information architecture and experience

### Authenticated navigation

The responsive application shell SHALL provide Dashboard, Resume Health, Career
Profile, Evidence Vault, Role Explorer, Job Match, Applications, Interview Prep,
Networking, Career Growth, Analytics, and Settings. It SHALL support expanded and
collapsed desktop states, a mobile drawer, active-page indication, keyboard
navigation, and accessible labels.

The reference image directs hierarchy, card density, spacing, and module layout.
The production visual language is a light neutral canvas, white cards, dark navy
navigation, indigo/purple primary action, green verified/strong states, amber
warnings/moderate states, and red only for critical gaps. Color never acts as the
only status signal.

Reusable primitives include AppShell, Sidebar, TopBar, PageHeader, MetricCard,
ScoreRing/ScoreBar, StatusBadge, Empty/Loading/Error states, DataTable, FilterBar,
Tabs, Drawer, Modal/ConfirmDialog, Timeline, KanbanBoard, DiffViewer,
EvidenceBadge, RequirementMatrix, ResumePreview, FileUploadDropzone,
NotificationCenter, and CommandSearch. A primitive is introduced with the first
real consumer, not as an untested placeholder library.

### Accessibility and responsive behavior

- **PR-A11Y-001:** All product and public pages SHALL target WCAG 2.2 AA.
- **PR-A11Y-002:** Primary workflows SHALL be fully keyboard operable with visible
  focus, semantic structure, named controls, described errors, and focus-managed
  dialogs.
- **PR-A11Y-003:** Charts SHALL include a text/table summary, and color SHALL NOT
  be the only information channel.
- **PR-A11Y-004:** Motion SHALL respect reduced-motion preferences.
- **PR-A11Y-005:** Reorder operations SHALL provide a non-drag control.
- **PR-A11Y-006:** Large desktop, laptop, tablet, and mobile are supported. The
  editor may optimize for desktop, but review and approval remain usable on mobile.

### Common feature behavior

Every completed feature includes server-side authorization, input validation,
loading/empty/success/error states, responsive and keyboard-accessible UX, tests,
documentation, migration when data is persisted, API contract, safe failure,
audit events where relevant, and real application state. Hardcoded values are
limited to isolated, explicitly fictional fixtures.

## Public website

- **PR-PUBLIC-001:** Provide landing, product, features, how-it-works, resume
  health entry, pricing, security/privacy, scoring methodology, responsible AI,
  about, contact, terms placeholder, privacy placeholder, login, and registration.
- **PR-PUBLIC-002:** The landing page explains the product value, general health,
  Evidence Vault, role readiness, exact job matching, Change Studio, verified
  export, application workflow, interview readiness, trust/privacy, pricing, FAQ,
  and a final call to action.
- **PR-PUBLIC-003:** Testimonials SHALL be real and consented or prominently
  labeled demo placeholders. Fabricated customer endorsements are prohibited.
- **PR-PUBLIC-004:** Prices and entitlements SHALL come from configuration or
  database records rather than repeated frontend constants.

## Onboarding

The onboarding sequence is account or guest health check; resume upload; parsed
information review; uncertain-field correction; target-role selection; location,
work model, seniority, industry, language, and writing preferences; then
dashboard. Nonessential steps are skippable and resumable. Guest data cannot be
silently converted or retained without explicit account linkage and consent.
Upload, processing, typed-review, and analysis completion are server-observed
owner-scoped state. The browser may save intent and explicit skips but cannot
assert those pipeline transitions.

## Functional module requirements

### Module 1 — General Resume Health (Phase 2)

- Accept initial PDF and DOCX uploads for guests and registered users; guests get
  one limited, short-lived report, while registered users may save and act on it.
- Validate extension-independent MIME/signature, configurable size/page limits,
  malware and expansion behavior; store with randomized private keys.
- Extract text and layout through replaceable providers, detect image-only files,
  and record sections, contact data, experience, education, skills, projects,
  certifications, bullets, source spans, and confidence in a canonical model.
- Run parsing and reporting asynchronously and expose status to the frontend.
- Show overall health, ATS Readiness/Machine Readability, Recruiter Clarity,
  Content Impact, Achievement Strength, Structure, Consistency, Truth and
  Confidence, issues, quick wins, section feedback, plain text, reading order, and
  parsing-confidence warnings.
- Allow user correction of uncertain structured fields before downstream use.

The system SHALL not depend on one parser. It provides local implementations and
interfaces for parsing, text, layout, malware, and OCR providers.

### Module 2 — Career Profile (Phase 3)

- Maintain personal information, summary, employment, education, skills,
  projects, certifications, publications, awards, volunteering, languages,
  portfolio links, authorization, location, industries, roles, and work style.
- Experience stores official/display title, employer, dates, location/type,
  description, achievements, skills, projects, evidence, confirmation, and source
  provenance.
- Provide timeline/list views, CRUD, accessible reorder, conflict detection,
  promotion grouping, concurrent roles, and neutral gap indication.
- A resume import proposes typed profile changes from the owned reviewed semantic
  snapshot; it does not silently overwrite the durable profile. Canonical facts,
  entities, and skills expose explicit confirmation and per-field provenance.
  Material edits revoke confirmation, and relationship edges remain
  owner-scoped.

### Module 3 — Evidence Vault (Phase 3)

- Store resume statements, confirmed achievements, metrics, projects,
  certificates, publications, awards, review excerpts, portfolio/GitHub links,
  testimonials, support documents, and notes.
- Each record includes title/description, organization/project, date range,
  skills, metrics, source type/document/span, attachment, confirmation,
  verification state, confidence, and timestamps.
- States are Verified, Confirmed, Supported, Inferred, and Unsupported, with
  explicit transition/audit rules.
- Users can create/edit/confirm/archive, upload support, connect evidence to
  experiences/skills/requirements, and see every downstream use.

### Module 4 — Achievement Inbox (Phase 3)

- Provide quick add, guided questions, monthly check-ins, draft evidence, metric
  clarification, employer/project association, reminders, and timeline.
- Ask what was delivered, the problem/change/audience/measurement, effects on
  time/money/risk/effort, collaboration/leadership, and methods/technology.
- Only confirmed answers convert into eligible Evidence Vault items; unanswered
  prompts remain unanswered.

### Module 5 — Role Explorer (Phase 4)

- Search a seeded, versioned role taxonomy by title, seniority, industry,
  location, optional company type, and domain; preserve an external-provider
  interface.
- Analyze competency coverage, responsibility/seniority, leadership, domain,
  technical skills, business impact, education/credentials, and evidence strength.
- Represent demonstrated, listed-not-demonstrated, transferable, adjacent,
  missing, unknown, required, and helpful skill states.
- Save and compare up to three roles; show evidence-linked strengths/gaps,
  transition guidance, history, and next actions without hiring-probability claims.

### Module 6 — Job Match (Phase 5)

- Import pasted text, an authorized safe URL, a saved job, or manual fields. A
  browser extension is a later adapter.
- URL import allows HTTP(S), validates DNS destinations and every redirect,
  blocks non-public networks, limits time/redirects/bytes, sanitizes content, and
  never executes remote scripts.
- Extract explicit job metadata and requirements. Every requirement stores its
  original source span, normalized form, type, importance, mandatory/preferred
  classification, and confidence.
- Show a matrix of requirement, importance, user state, match type, evidence
  strength/records, and action. Match states are Strong, Partial, Transferable,
  Unknown, Missing, and Not Applicable.
- Compute versioned Requirement Coverage, Responsibility, Seniority, Domain,
  Evidence, ATS, Human Readability/Content Impact, Truth Confidence, and
  Application Readiness, with mandatory gaps outside the average.

### Module 7 — Opportunity Prioritizer (Phase 5)

Use coverage, mandatory gaps, evidence, career direction, user interest,
compensation/location/work-model preferences, deadline, tailoring effort, and
existing contacts to explain Pursuit Priority, reasons for/reconsidering,
blockers, preparation effort, and next action. It SHALL not say the user will or
will not be hired.

### Module 8 — Change Studio (Phase 6)

- Show original/suggested text, word diff, reason, evidence, requirement,
  confidence, risk, expected internal score effect, and confirmation need.
- Represent grammar/format, evidence rewrite, reorder, evidence-backed addition,
  deletion, confirmation-required, and prohibited unsupported changes as typed
  operations targeted at stable document item IDs.
- Support accept/reject/edit, alternate/shorter/technical/executive options,
  preserve wording, section lock, policy-limited safe batch, undo/redo, and restore.
- Persist immutable versions and never mutate a prior export.

### Module 9 — Truth-Locked AI (Phase 6)

- Provide an environment-selected production provider and deterministic fake for
  requirement extraction, classification, change suggestions, rewrites,
  questions, grounding, application answers, interview questions, and STAR
  outlines.
- Require strict structured output, schema validation, bounded retry/timeout,
  model/prompt versions, usage/cost, rate limits/budgets, and redacted logs.
- Treat document text as untrusted data; separate it from instructions, handle
  Unicode controls safely, reject malformed output, and never execute or directly
  place model output in a shell/SQL/HTML/file path.
- Before display, verify every claim/number/technology/credential against
  evidence, ensure employer/title/date consistency, preserve contribution and
  meaning, and reject unsupported output.

### Module 10 — Resume Builder (Phase 7)

- Edit structured fields/sections/bullets, reorder accessibly, add only grounded
  bullets, preview live/page/plain-text/recruiter scan, control safe layout bounds,
  autosave, compare versions, and restore.
- Supply Standard Professional, Compact Technical, Executive, Graduate, and
  Consulting/Finance templates.
- Templates are primarily single-column, avoid text boxes and essential
  header/footer content, use text rather than icon-only facts, standard section
  names, searchable output, predictable reading order, PDF/DOCX support, and one-
  or two-page layouts.

### Module 11 — Verified Export (Phase 7)

- Render PDF, DOCX, plain text, and structured JSON asynchronously from an exact
  immutable version.
- Parse PDF/DOCX again and compare name, contact, employers, titles, dates,
  education, skills, bullets, section order, searchability, reading order,
  omissions/duplication, and unsupported claims.
- Store and display pass/fail, detected/missing fields, reading order, grounding,
  file hash, source version, and generation time. Block critical failures and
  clearly warn on allowed noncritical failures.

### Module 12 — Application Pack (Phase 8)

For a job, generate a grounded tailored resume, cover letter, professional bio,
interest/fit answers, recruiter/hiring-manager/referral/network/follow-up messages,
interview introduction, and achievement summary. Detect conflicting dates,
titles, metrics, unsupported answer claims, and resume/letter/interview
inconsistencies.

### Module 13 — Application Workspace (Phase 8)

- Track Saved, Researching, Preparing, Ready to apply, Applied, Recruiter screen,
  Interview, Assessment, Offer, Rejected, and Withdrawn stages.
- Provide accessible Kanban plus table and calendar, CRUD/stage changes,
  deadlines/follow-ups, contacts, notes, tasks/events, pinned resume and letter,
  answers, referrals, interviews, outcomes/reasons/offers, search/filter/sort.
- Do not autonomously submit applications in the first production release.

### Module 14 — Interview Prep (Phase 9)

Provide a Resume Defense Map, STAR story library, role questions, mock-session
structure, notes/reflection, and grounded follow-up. Each important claim can link
evidence, situation/task/action/result, personal contribution, metric explanation,
likely questions, and confidence. Warn when a strong claim lacks a defensible
story. Revalidate live canonical evidence eligibility and exact current revision
pins before creating a new generated question bank or follow-up.

### Module 15 — Networking CRM (Phase 9)

Store contacts, organizations, relationship stage, last/next contact, notes,
referral state, templates, history, reminders, tags, and search/filter. Collection
storage, and outreach require separate purpose-specific consent; private contacts
are not scraped. Collection/storage withdrawal tombstones parent PII and all
child personal/free-text content while retaining only required content-free
consent/audit/queue state. Outreach-only withdrawal preserves private notes and
inbound/mutual history that is neither template-linked nor referral-related
while removing outbound/template/referral/reminder material.

### Module 16 — Career Growth (Phase 9)

Provide goals, achievement history, skill-evidence view, promotion/internal-
mobility preparation, review summaries, learning/certification tracking,
quarterly/annual review, an annual resume-refresh workflow, and an explainable
career health score. Promotion Readiness is a preparation report over current
eligible evidence and owner-maintained records; it is not an employer decision,
promotion probability, guarantee, or assessment of job-market value.

### Module 17 — Analytics (Phase 9)

Show applications/stages, interviews/offers, response/interview/offer rates, role,
industry/source, pinned resume-version patterns, requirement trends, achievement
growth, and readiness history. Small cohorts show uncertainty/suppression where
needed; analysis is correlation, never causal proof. Reports define their
cohort, numerator/denominator, event timestamp, selected IANA timezone, and
suppression policy under a versioned metric definition. Achievement growth uses
current canonical eligibility, event buckets stay within the selected application
cohort, supplemental history is bounded, and freshness tracks the exact point set
for the report's guarded source window.

### Module 18 — Settings and Privacy (Phases 1–10)

Provide profile/account/password/sessions, notifications, language/region/writing,
AI and consent, retention, export/deletion, billing/connections, and security
activity. Defaults: no model training on user content, minimize provider payloads,
no raw content in analytics/logs, configurable retention, recorded consent,
document deletion, account export/deletion, and session invalidation.
Until an export, deletion, billing, connection, or notification-delivery workflow
is fully composed, Settings SHALL expose a server-owned disabled capability and
an honest unavailable state rather than a simulated action.

## Administration and commercial requirements

- Admins can view system/job health, redacted failures, safe retries, aggregate
  metrics, plans/flags, taxonomy/templates, and audit records.
- Admins SHALL NOT gain unrestricted raw-resume access by role alone. Every
  sensitive action is purpose-bound, least-privilege, and audited.
- Plans are Free, Job Hunt Sprint, Pro, and Coach/Organization. Entitlements and
  quotas—not frontend conditionals—control features. Prices are centrally
  configured and billing webhooks idempotent.
- Production deployment requires a protected environment and manual approval.

## Data and privacy requirements

- Use UUID identifiers and ownership on all user data; validate tenant and user
  authorization for every object, API, background task, signed URL, and export.
- Store consent records and data-use purpose. Provide data inventory, portability,
  document deletion, account erasure scheduling, and configurable lifecycle.
- Encrypt in transit and at rest; store passwords/tokens using the dedicated
  secure mechanisms in the architecture; never commit secrets.
- Preserve source spans, confidence, confirmation, model/prompt/score versions,
  and audit history required to explain a result.
- Do not soft-delete every table. Use it only where restore, retention, audit, or
  asynchronous cascade requires a tombstone.

## Operational requirements

- Background jobs include malware, parse/OCR/analyze, job extraction/match,
  change/grounding, render/verify, email/reminders, analytics, and retention.
- Every job has an idempotency key, ownership, timeout, bounded retry, dead-letter
  behavior, status/progress where useful, trace ID, and AI cost metadata.
- Structured telemetry includes request/trace IDs, service health/readiness, queue
  depth/age, processing and provider latency/failure/cost, rate-limit events, and
  authentication failures without raw career content.
- CI covers dependency install, format, lint, types, unit/integration, web build,
  API startup/import, migration validation, security scans, container build, and
  an end-to-end smoke test. Production deploy is never automatic without a
  protected environment.

## Critical acceptance requirements

The release test portfolio SHALL prove:

1. Changing an ID cannot expose another user's resume or object.
2. An unsupported claim cannot enter a generated resume.
3. A generated number maps to confirmed evidence.
4. Embedded job/resume instructions cannot override system policy.
5. Malformed, disguised, oversized, and hostile uploads fail safely.
6. A generated export parses back with critical fields and claims intact.
7. An earlier resume version can be restored without mutating history.
8. A user can delete an uploaded document across active stores according to policy.
9. Account deletion removes or schedules all owned data according to policy.
10. Every primary workflow is keyboard accessible.

Test fixtures cover one/two-column, DOCX, headers/footers, tables, image-only,
date variants, concurrent roles/promotions/gaps, long/malformed/wrong-extension/
oversized files, and prompt injection in resumes and job descriptions.

## Phase 0 product slice

Phase 0 delivers the navigable, accessible visual foundation and fictional
dashboard preview, service health, dependency readiness, contracts, and test
seams. It does not process user career data or return a real readiness analysis.
Preview values must be clearly fictional and must not use product API shapes that
could accidentally become an undocumented contract.

Phase 0 product verification is limited to startup, health, responsive/accessibility
smoke coverage, truthful labeling, and quality gates. Functional acceptance for
the requirements above belongs to the phase mapping in `PLANS.md` and
`docs/implementation-checklist.md`.

## Open product decisions

These decisions are intentionally deferred and must be resolved before their
owning phase exits:

- default upload size/page and guest retention limits (Phase 2);
- exact evidence-state transition authority and independent verification sources
  (Phase 3; resolved by ADR 0009: user confirmation cannot produce `Verified`,
  and no independent verifier is configured in Phase 3);
- licensed role taxonomy and regional job-source policy (Phases 4–5);
- AI provider/data residency, prompt retention, and per-plan cost budgets (Phase 6);
- renderer/template licensing and critical round-trip thresholds (Phase 7);
- contact consent/import policy and outcome cohort suppression (Phase 9;
  resolved by ADR 0015: explicit owner attestation is recorded separately for
  collection/storage/outreach, no contact is scraped or backfilled as consent,
  and rates/averages are suppressed below five records);
- pricing, payment provider, production regions, RPO/RTO, retention, support/admin
  access, and legal texts (Phase 10).

None of these open choices permits weakening the truth, user-control, security,
privacy, or score-language rules.
