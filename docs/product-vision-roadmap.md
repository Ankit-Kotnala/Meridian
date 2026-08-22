# Rezumi product vision roadmap

Status: living document aligned with [ADR 0019](adr/0019-activation-first-workspace-and-assisted-application-supply-chain.md)  
Last updated: 2026-08-23

## What you are building

Rezumi helps people whose resumes get rejected understand **what they have actually achieved**, **where they stand against real roles**, and **how to close gaps** — without inventing facts or applying on their behalf without consent.

The emotional goal is real: rejected candidates should see that their experience **counts**, is **backed by proof**, and can be **presented honestly** to employers.

## How your vision maps to the platform

| Your idea | Rezumi approach | Phase | Status |
| --- | --- | --- | --- |
| Upload resume; check every detail | Resume Health parse + field review + health report | 2 | **Shipped** |
| Pull LinkedIn/GitHub/cert links from resume | Parser stores declared links as personal facts | 3 | **Shipped** |
| Visit those links and import achievements as evidence | Declared-link enrichment (`DeclaredProfileConnector`) | 11 | **In progress** |
| LinkedIn profile scraping | **Out of scope** — LinkedIn prohibits automated collection (ADR 0019) | — | Rejected |
| GitHub / public portfolio / cert pages | Public API or permitted HTTP read → user-reviewed proposals | 11 | **In progress** (GitHub + portfolio shipped) |
| Scrape all jobs on the internet | Published ATS APIs + licensed feeds + paste/URL import | 12 | Planned |
| Filter jobs to user's target role | Role Readiness + Job Match prioritizer | 4–5 | **Shipped** |
| Store portal passwords; apply automatically | **Out of scope** — credential breach class + ToS (ADR 0019) | — | Rejected |
| One-click apply with pre-filled answers | Application Profile + assisted handoff pack | 12 | Planned |
| Market gap assessment | Role Readiness competency gaps (deterministic) | 4 | **Shipped** |
| Guided upskilling path | Gap → `career_growth` learning items → evidence loop | 13 | Planned |

## Non-negotiable product rules (why we do not auto-scrape LinkedIn or auto-submit)

1. **Truth-lock** — Every claim must cite eligible evidence. Scraped text becomes a **proposal** the user confirms; it never silently becomes fact.
2. **Third-party terms** — LinkedIn and many job boards prohibit automated collection. Rezumi uses **published APIs** and **user-declared public links** instead.
3. **Candidate safety** — Storing Naukri/LinkedIn/Workday passwords would make Rezumi a high-value breach target. **Assisted apply** pre-fills what it can; **the user submits** in their own browser session.
4. **No fake scores** — Internal Resume Health Score and match scores are for the user's planning only, never employer/ATS ratings.

## Implementation phases (execution order)

### Phase 11 — Declared-link evidence enrichment *(current)*

**Goal:** When a resume lists `github.com/you` or a public portfolio, Rezumi reads **only that declared URL**, extracts public achievements, and creates **achievement drafts + evidence** with source URL and excerpt. User confirms before anything is citable.

Deliverables:

- [x] `DeclaredProfileConnector` port + deterministic fake (local dev, no credentials)
- [x] GitHub public profile connector (REST API, no login)
- [x] Public portfolio HTML connector (SSRF-safe fetch)
- [ ] Certification / personal-site connectors where terms permit
- [ ] Async worker + outbox (mirror attachment workflow)
- [ ] UI: “Import from this link” on profile links
- [ ] Corp ID persisted column + API standing

### Phase 12 — Opportunity supply and assisted apply

**Goal:** Jobs matched to the user's target role from **licensed/published sources**; applying takes one focused click, not forty form fields.

Deliverables:

- [ ] `JobSourceConnector` (Greenhouse, Lever, Ashby, …) + fixtures
- [ ] Role-targeted job feed on Opportunities home
- [ ] `ApplicationProfile` (work auth, notice period, salary band, locations)
- [ ] Assisted apply pack: tailored resume + pre-answered questions + handoff link

### Phase 13 — Gap-to-learning loop

**Goal:** After a job match or role readiness analysis, show **what you lack** and a **concrete learning path** — not vague advice.

Deliverables:

- [ ] Read gaps from `role_readiness` → open `career_growth` development items
- [ ] Completing an item prompts evidence upload, closing the loop
- [ ] Dashboard “Your growth path” section tied to real gap data

## What is already working today

- Resume upload → parse → review → health report → career record import
- Evidence Vault + Achievement Inbox (including resume bullet materialization)
- Role Explorer + Job Match against saved postings
- Application tracking + grounded application packs
- Interview prep, networking reminders, career growth goals, analytics
- Activation-first dashboard (user-centric home)

## Success metrics (honest)

- User sees **their** roles, skills, evidence counts on dashboard within seconds
- Declared GitHub link → N achievement drafts with source excerpts in under 30s
- Job match shows **matched vs gap** requirements with evidence citations
- Assisted apply reduces time-on-form; user still clicks Submit
- Gap analysis produces ≥1 actionable learning item per critical gap

## Next engineering slice (this sprint)

1. Finish Phase 11 GitHub enrichment API + career profile UI action
2. Add dashboard copy explaining “Import achievements from your links”
3. Begin Phase 12 `ApplicationProfile` schema + CRUD
4. Wire Phase 13 read-only gap summary on Growth home

See `PLANS.md` for verification gates and `[x]`/`[ ]` checklist status.
