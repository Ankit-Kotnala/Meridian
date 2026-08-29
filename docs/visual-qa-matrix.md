# Rezumi product-wide visual QA matrix

Status: redesign verification record
Run date: 2026-07-27
Environment: production Next.js image behind the local `web-edge` container at
`http://localhost:3000`, with the real local FastAPI, PostgreSQL, Redis, MinIO,
Mailpit, ClamAV, Celery worker, and scheduler services.

This record distinguishes automated browser evidence from human visual review.
The Windows browser sandbox could not apply its read ACLs, so the connected
interactive browser and direct local-image viewer could not open. Playwright
completed the repeatable route, interaction, reflow, focus, error,
reduced-motion, and lab performance checks below. Representative landing
desktop/mobile and protected Applications mobile captures were manually
inspected through a sandbox-safe encoded-preview path; exhaustive manual review
of every saved screenshot is not claimed.

The final production-mode completion rerun on 2026-07-27 passed all 28 public
route/viewport cases and all 168 protected route/viewport cases. It reported no
horizontal overflow, console errors, page errors, reduced-motion failures, or
lab-threshold regressions. The protected pass used a fresh fictional local
account through the healthy FastAPI, PostgreSQL, Redis, MinIO, Mailpit, ClamAV,
worker, and scheduler stack.

## Required viewport matrix

| Viewport | Height used | Intent                                           | Result                                         |
| -------: | ----------: | ------------------------------------------------ | ---------------------------------------------- |
|   320 px |      720 px | Narrow mobile and 200% desktop-equivalent reflow | Pass                                           |
|   360 px |      780 px | Common small mobile                              | Pass                                           |
|   393 px |      852 px | Current compact mobile                           | Pass                                           |
|   768 px |     1024 px | Tablet portrait                                  | Pass                                           |
|  1024 px |      900 px | Tablet landscape / compact desktop               | Pass                                           |
|  1440 px |     1000 px | Standard desktop                                 | Pass after Applications filter-grid correction |
|  1920 px |     1080 px | Wide desktop                                     | Pass                                           |

Each automated capture requires a 200 response, no page or console error, no
horizontal page overflow, the skip link as the first keyboard target, and
`prefers-reduced-motion` taking effect. Authenticated mobile captures also open
and close the workspace navigation using its visible controls.

## Route and state coverage

Legend: **7/7** means every required viewport passed. **Component/E2E** means a
dynamic detail screen was exercised by its focused component or journey test,
but a stable visual fixture was not available. Those rows are not described as
seven-viewport visual passes.

| Area                               | Routes or states                                                                                                                                            | Automated coverage                                                           | Result / note                                                                                                                                                                                             |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Public home                        | `/`                                                                                                                                                         | 7/7 + saved screenshots                                                      | Pass; enterprise landing rerun passed at every required width                                                                                                                                             |
| Product information                | `/product`, `/features`, `/how-it-works`, `/security`, `/privacy`, `/terms`, `/accessibility`, `/pricing`, `/about`, `/contact`, `/resources`, `/changelog` | `/product` 7/7; all slugs share the same generated route and document layout | Pass; availability and preview language remain explicit                                                                                                                                                   |
| Fictional demo                     | `/demo/dashboard`                                                                                                                                           | 7/7 + saved screenshots                                                      | Pass; fictional label and scoring disclaimer visible                                                                                                                                                      |
| Authentication                     | `/login`, `/register`, `/forgot-password`, `/reset-password`, `/verify-email`, `/get-started`                                                               | 7/7 each; desktop/mobile auth journey                                        | Pass after reserving verification-state height to remove mobile CLS                                                                                                                                       |
| Guest Resume Health                | `/resume-health/guest`                                                                                                                                      | 7/7 + saved screenshots                                                      | Pass; public shell, retention, empty/upload and failure behaviors retained                                                                                                                                |
| Guest processing, review, report   | `/resume-health/guest/processing/[jobId]`, `/review/[documentId]`, `/report/[analysisId]`                                                                   | Component/E2E                                                                | Dynamic records require an uploaded document; no stable visual fixture committed                                                                                                                          |
| Workspace shell                    | all protected routes, grouped navigation, desktop account menu, mobile drawer                                                                               | 24 routes x 7 viewports; auth journey                                        | Pass; mobile drawer interaction included                                                                                                                                                                  |
| Dashboard and onboarding           | `/dashboard`, `/onboarding`                                                                                                                                 | 7/7 each; auth journey                                                       | Pass; data-truthful empty/setup states. The 2026-08-16 workspace-home revamp was re-checked at 1440 px and 420 px in light and dark from a static render only; the seven-width stack rerun is outstanding |
| Career record                      | `/career-profile`, `/career-profile/imports`, `/evidence`, `/achievement-inbox`                                                                             | 7/7 each                                                                     | Pass; provenance and approval surfaces preserved                                                                                                                                                          |
| Career record details              | `/career-profile/imports/[proposalId]`, `/evidence/[evidenceId]`                                                                                            | Component/unit suites                                                        | Dynamic proposal/evidence fixtures were not stable visual inputs                                                                                                                                          |
| Opportunity intelligence           | `/role-explorer`, `/job-match`                                                                                                                              | 7/7 each; focused E2E                                                        | Pass visually; the full-stack journey has one stale assertion expecting tailoring despite a truthful mandatory-gap result                                                                                 |
| Applications                       | `/applications`                                                                                                                                             | 7/7 after targeted rerun; component/E2E                                      | Pass; 1440 px filter overflow was found, corrected, rebuilt, and rerun                                                                                                                                    |
| Application detail                 | `/applications/[applicationId]`                                                                                                                             | Component/unit and full-stack journey                                        | UI tests pass; end-to-end creation is blocked by the existing API `resume_builder_conflict` response                                                                                                      |
| Resume creation                    | `/resume-builder`, `/change-studio`                                                                                                                         | 7/7 each; unit/E2E                                                           | Visual pass; Change Studio journey passes. Resume Builder full-stack creation remains blocked by the API conflict above                                                                                   |
| Account Resume Health              | `/resume-health/account`                                                                                                                                    | 7/7; auth journey                                                            | Pass                                                                                                                                                                                                      |
| Account processing, review, report | `/resume-health/account/processing/[jobId]`, `/review/[documentId]`, `/report/[analysisId]`                                                                 | Component/E2E                                                                | Covered in authenticated journey where a record is created; no committed stable-ID visual fixture                                                                                                         |
| Interview preparation              | `/interview-prep`                                                                                                                                           | 7/7                                                                          | Pass                                                                                                                                                                                                      |
| Interview details                  | `/interview-prep/sessions/[sessionId]`, `/stories/[storyId]`                                                                                                | Component/unit                                                               | Dynamic detail fixtures not used for seven-viewport capture                                                                                                                                               |
| Networking                         | `/networking`                                                                                                                                               | 7/7                                                                          | Pass                                                                                                                                                                                                      |
| Contact detail                     | `/networking/contacts/[contactId]`                                                                                                                          | Component/unit                                                               | Dynamic contact fixture not used for seven-viewport capture                                                                                                                                               |
| Growth and analytics               | `/career-growth`, `/analytics`                                                                                                                              | 7/7 each                                                                     | Pass; analytics retain correlation and small-cohort language                                                                                                                                              |
| Settings                           | `/settings`, `/security`, `/sessions`, `/notifications`, `/connections`, `/consent`, `/privacy`, `/billing` under `/settings`                               | 7/7 each; auth journey covers session controls                               | Pass; unavailable capabilities are labeled rather than simulated                                                                                                                                          |
| Framework states                   | route loading, empty, error and not-found boundaries                                                                                                        | Unit/component suites and production build                                   | Pass where implemented; important data views retain loading, empty, failure, and success paths                                                                                                            |

## Automated results

### Public evidence committed with this branch

- 28 redesigned captures: four representative public workflows at seven
  viewports, all 200, no horizontal overflow, console error, or page error.
- Lab LCP observation: 116–792 ms.
- CLS: 0 across the committed redesigned captures.
- Event Timing maximum: 32 ms across 64 observed interaction events.
- Largest encoded JavaScript observation: 208,134 bytes (about 203 KiB).
- Six additional public/auth routes were checked at all seven viewports. A CLS
  issue on `/verify-email` at 320 and 360 px was corrected and both affected
  widths passed the targeted rerun.

### Enterprise landing rerun

- The redesigned `/` route was rerun at 320, 360, 393, 768, 1024, 1440, and
  1920 px against the isolated Next.js development server.
- All seven captures returned 200 with no horizontal overflow, console error, or
  page error. Skip-link focus and reduced-motion checks passed.
- CLS was 0 at every width. Observed LCP ranged from 292 to 884 ms and the
  maximum Event Timing duration was 32 ms.
- The focused report is saved as
  `screenshots/ux-redesign/after/landing-enterprise-qa-results.json`.

### Interaction-polish rerun

- The current landing, fictional demo, login, and guest Resume Health surfaces
  completed 28/28 development-server captures across all seven widths with no
  overflow, console error, page error, or reduced-motion failure.
- The optimized landing, fictional demo, and login surfaces completed 21/21
  captures across all seven widths with no overflow, console error, page error,
  or reduced-motion failure.
- Optimized observations: maximum LCP 1008 ms, CLS 0, maximum Event Timing 40 ms,
  and maximum encoded JavaScript 236,893 bytes. The route-scoped Motion provider
  keeps the dependency out of the root layout; the public header uses CSS motion.
- The reports are saved as
  `screenshots/ux-redesign/after/interaction-polish-dev-qa-results.json` and
  `screenshots/ux-redesign/after/interaction-polish-production-qa-results.json`.
- The API-dependent guest surface later returned a truthful 503 after Docker
  Desktop became unavailable. That stopped-daemon observation is not represented
  as a frontend or accessibility pass, and does not replace the successful
  28-capture development rerun completed while the API was available.

### Authenticated workspace

- 168 captures: 24 protected top-level routes at seven viewports.
- All returned 200 with no page or console error; keyboard skip-link and reduced
  motion checks passed.
- One 1440 px Applications overflow was found. The filter layout now changes
  from two columns to three at `xl`, using the fixed seven-column arrangement
  only at `2xl`. Its seven-viewport production rerun passed with zero failures.
- Workspace lab observations before that single layout correction: LCP 96–620
  ms, maximum CLS 0.0043, maximum Event Timing duration 40 ms across 841 events,
  and maximum encoded JavaScript 377,491 bytes. The targeted corrected route
  observed CLS 0 and a 32 ms maximum interaction duration.

These are local lab observations, not field Core Web Vitals. Event Timing is a
useful interaction proxy but is not a field INP percentile. No production RUM
was available, so no field-performance claim is made.

## Screenshot evidence

The [before folder](screenshots/ux-redesign/before/) contains home and demo
captures at 393 and 1440 px plus the baseline JSON report. The baseline fictional
demo had horizontal overflow at 393 px.

The [after folder](screenshots/ux-redesign/after/) contains home, fictional demo,
login, and guest Resume Health captures at every required viewport plus the full
[automated report](screenshots/ux-redesign/after/qa-results.json). Useful direct
comparisons include:

- [Home before, 393 px](screenshots/ux-redesign/before/home-393.png) and
  [home after, 393 px](screenshots/ux-redesign/after/home-393.png)
- [Home before, 1440 px](screenshots/ux-redesign/before/home-1440.png) and
  [home after, 1440 px](screenshots/ux-redesign/after/home-1440.png)
- [Demo before, 393 px](screenshots/ux-redesign/before/demo-393.png) and
  [demo after, 393 px](screenshots/ux-redesign/after/demo-393.png)
- [Login after, 320 px](screenshots/ux-redesign/after/login-320.png) and
  [login after, 1920 px](screenshots/ux-redesign/after/login-1920.png)
- [Protected Applications after, 393 px](screenshots/ux-redesign/after/applications-393.png)

The current landing desktop/mobile and protected Applications mobile captures
were manually inspected through the encoded-preview fallback. The remaining
saved screenshots retain automated review only.

## Repeatability

`frontend/web/scripts/capture-visual-qa.mjs` owns the viewport catalog, route catalog,
authenticated account setup, focus/reflow/error checks, mobile navigation
interaction, screenshots, and JSON report generation. Example:

```powershell
npm exec --workspace=@rezumi/web -- node scripts/capture-visual-qa.mjs `
  --baseUrl=http://localhost:3000 `
  --authenticated=true `
  --mailpitUrl=http://localhost:8025 `
  --screenshots=false
```

For an isolated renderer whose port is not in the backend CSRF allow-list, pass
`--authBaseUrl=http://localhost:3000` to authenticate through the approved local
edge origin and reuse the resulting localhost session while capturing the
isolated `--baseUrl`. This preserves the CSRF policy instead of weakening it for
visual QA.

## Known verification constraints

- Connected interactive-browser and direct local-image inspection remain blocked
  by a Windows sandbox ACL helper error. Representative captures were reviewed
  through a sandbox-safe encoded-preview fallback; automated checks and that
  bounded review are not a substitute for exhaustive aesthetic inspection.
- Dynamic detail routes do not have stable production-like fixture IDs. Their
  component and journey coverage is identified explicitly in the matrix.
- Several full-stack Resume Builder and downstream Application journeys receive
  the API's existing `409 resume_builder_conflict` response for newly registered
  users after evidence confirmation. This redesign does not change that backend
  domain behavior or describe those journeys as passing.
- The Job Match full-stack expectation conflicts with the deterministic, honest
  output for a mandatory gap. The UI correctly says to address mandatory gaps
  before tailoring; the stale assertion is not used to weaken the truthful
  product rule.
