# CareerOS product design system

Status: active baseline for the 2026 product-wide UX redesign
Last reviewed: 2026-07-26

## Product direction

CareerOS is a calm, evidence-first career operating system. The interface should
feel like a trustworthy working record: text-first, precise, reversible, and
quiet enough for high-stakes review. The structured Career Profile and its
evidence graph remain the source of truth; resumes, application materials,
messages, interview stories, and analytics are derived views.

The visual direction is light-only. Warm neutral surfaces and forest green
provide continuity, while blue is reserved for keyboard focus. Red appears only
for destructive actions or critical gaps. Color always has a text or icon
equivalent. Gradients, decorative metric cards, invented activity, fake customer
logos, and vague “magic” affordances are not part of the system.

CareerOS currently uses a system-native font stack because the repository does
not include an approved self-hosted font asset. Introducing a network font would
add a privacy, reliability, and layout-shift dependency. A future font change
must use a reviewed local asset through `next/font/local` and preserve the
metrics of the current stack.

## Current product-pattern research

This redesign reviewed current official guidance on 2026-07-26. The sources are
inputs, not visual templates:

- [Linear Method](https://linear.app/method/introduction): reduce work about
  work, keep workflows fast, and make the system opinionated enough to guide the
  next action.
- [GitHub Primer foundations](https://primer.style/product/getting-started/),
  [navigation](https://primer.style/product/ui-patterns/navigation/),
  [layout](https://primer.style/product/getting-started/foundations/layout/), and
  [forms](https://primer.style/product/ui-patterns/forms/): use durable layout
  regions, predictable navigation, explicit labels, and restrained component
  variation.
- [GitHub Primer accessibility guidance](https://primer.style/accessibility/design-guidance/):
  accessibility starts in design, with keyboard access, clear focus, meaningful
  names, and non-color cues.
- [Atlassian empty state](https://atlassian.design/components/empty-state/) and
  [accessibility foundations](https://atlassian.design/foundations/accessibility):
  explain why a collection is empty and provide one relevant next step.
- [GOV.UK validation](https://design-system.service.gov.uk/patterns/validation/):
  validate when the user can act on an error, keep entered values, identify the
  field in error, and never rely on color alone.
- [Notion Agents](https://www.notion.com/product/agents): make automated work
  visible, scoped, and reviewable. CareerOS applies this as explicit sources,
  immutable snapshots, and accept/reject paths rather than autonomous mutation.
- [Greenhouse MyGreenhouse stages](https://www.greenhouse.com/product-features/mygreenhouse-stages):
  make process stages and candidate-owned next steps legible. CareerOS applies
  this to application stage, deadline, follow-up, and exact document-version
  traceability.

The resulting CareerOS pattern is a grouped workspace shell, contextual page
headers, progressive disclosure for advanced detail, visible provenance beside
decisions, and one honest next step instead of an array of decorative summaries.

## Foundations

The canonical CSS values live in
`packages/design-tokens/src/tokens.css`. Product code uses semantic token names,
not raw palette values.

### Color roles

| Role          | Token                                             | Intended use                                           |
| ------------- | ------------------------------------------------- | ------------------------------------------------------ |
| Canvas        | `--background`                                    | Product and public page background                     |
| Surface       | `--surface`, `--surface-raised`                   | Cards, panels, controls                                |
| Quiet surface | `--surface-subtle`, `--surface-inset`             | Grouping, table headers, read-only detail              |
| Text          | `--foreground`, `--muted`, `--muted-strong`       | Primary and supporting text                            |
| Structure     | `--border`, `--border-strong`                     | Boundaries and input affordances                       |
| Brand/action  | `--primary`, `--primary-strong`, `--primary-soft` | Primary action, current navigation, selected state     |
| Shell         | `--navy`                                          | Authenticated navigation shell and document preview    |
| Status        | `--success`, `--warning`, `--danger`, `--info`    | Labeled semantic state only                            |
| Focus         | `--focus`                                         | Keyboard focus ring; remains distinct from brand state |

Evidence eligibility is shown as `Eligible`, `Needs review`, or `Ineligible` with
text, icon, and success/warning/danger treatment. Match states are `Covered`,
`Partially covered`, `Gap`, and `Not assessed`; never expose color alone. Chart
series use primary, info, warning, success, and muted-strong in that order, with
direct labels or a text summary. Red is not a routine series color.

### Type

- Display: `--font-family-display`; page titles use 26–32 px, 650 weight, tight
  tracking, and a short line length.
- Body: `--font-family-body`; default is 16 px with 1.6 line-height.
- Labels and controls: 13–14 px, 650–750 weight.
- Eyebrows: 11–12 px uppercase with restrained tracking; they provide context,
  not decoration.
- Numbers use tabular figures in tables and score details.
- Avoid all-caps body copy and repeated 800–900 weights. Hierarchy comes from
  spacing, contrast, and structure first.

### Space, shape, and elevation

The spacing rhythm is 4, 8, 12, 16, 20, 24, 32, 40, and 48 px. Dense forms and
tables use the lower half; page and section boundaries use the upper half.

- Controls use `--radius-control`.
- Cards and bounded data regions use `--radius-card`.
- Small tags use `--radius-small` or a full pill only when the value is a status.
- Borders carry most grouping. Shadows are restrained and never substitute for
  hierarchy.

### Motion

No motion dependency is installed. Current needs are satisfied by CSS color and
transform transitions of 150–200 ms. Route meaning, progress, validation, and
approval never depend on animation. `prefers-reduced-motion: reduce` removes
non-essential animation and collapses transition duration. New animated patterns
require a concrete comprehension benefit, reduced-motion behavior, and a bundle
impact review before a library is added.

## Layout and responsive behavior

Authenticated information architecture is grouped by user goal:

1. Overview
2. Career record
3. Opportunities
4. Create and prepare
5. Long-term growth

Setup Guide and Settings are utilities. The desktop shell has persistent grouped
navigation and a contextual top bar. Below the desktop breakpoint, navigation is
a keyboard-accessible modal drawer with a visible menu label and close action.

Pages use `PageHeader` for one H1, concise context, optional metadata, and at
most a small set of relevant actions. `SectionHeader` owns H2 hierarchy. Content
defaults to a readable 80rem measure; unusually dense workspace tables may use
96rem. Every route must remain operable at 320, 360, 393, 768, 1024, 1440, and
1920 px without horizontal page overflow. Wide tables live in a labeled
`.data-region.table-scroll`; core decisions must not require horizontal scrolling
on mobile.

Public pages use a simpler site header and footer. Authenticated navigation is
not reproduced in the fictional demo. Guest Resume Health uses a compact public
shell and short, explicit retention language.

## Components and ownership

Reusable presentation primitives belong in `packages/ui`. Domain behavior,
loading orchestration, API requests, and career-specific rules stay under
`apps/web/src/modules/<feature>`.

Current shared primitives include:

- Actions and inputs: `Button`, `Input`, `Select`, `CheckboxField`, `FieldLabel`.
- Structure: `Card`, `PageHeader`, `SectionHeader`, `Stepper`, `Tabs`.
- Data: `DefinitionList`, `Badge`, `Progress`.
- Feedback: `Alert`, `EmptyState`, `ErrorState`, contextual
  `LoadingSkeleton` variants, `ConfirmDialog`.
- Approval: `ApprovalPanel`, which keeps source, reason, evidence, audit
  consequence, and accept/reject controls together.

Do not create a shared primitive for a single feature variant. Promote a pattern
only after it appears in at least two domains and its semantics are stable.
`Card` is a neutral `div` by default; callers opt into `section`, `article`, or
`aside` only when the landmark is meaningful.

## Workflow patterns

### Loading, empty, failure, and success

Every data-driven view implements all four states. Loading skeletons mirror a
page, list, table, or form rather than showing an arbitrary gray rectangle. Empty
states say what is absent, why it matters, and the single safest next step.
Failure states preserve entered data where possible, name what failed, and offer
a bounded retry. Success feedback is announced through a polite live region and
does not hide the resulting state.

### Forms and validation

Use persistent visible labels. Placeholder text is an example, not a label.
Required state, format hints, and validation messages appear near the control and
are programmatically associated. Disable controls only when the reason is
obvious in the immediate state; otherwise explain the missing prerequisite.
Destructive actions use explicit confirmation and describe retained versus
deleted records.

### Provenance and approval

Generated factual material must show eligible evidence and immutable source
version. Material career-document changes expose original, proposal, reason,
requirement, evidence, and accept/reject/edit paths. Batch acceptance is limited
to eligible, low-risk changes and remains reviewable. Missing facts produce a
question, not plausible prose.

### Scores and analytics

Resume Health, job-specific match, and role readiness are distinct. Each surface
names its scope. Wherever an internal score could be mistaken for an external
assessment, show the canonical disclaimer from `docs/scoring-methodology.md`.
Analytics expose source watermarks and small-cohort suppression and state that
observed patterns are correlations, not causes or predictions.

## Accessibility baseline

Target WCAG 2.2 AA:

- One H1 and logical headings per page.
- Semantic links for navigation and buttons for actions.
- Full keyboard operation, visible focus, Escape support for modal navigation,
  and focus return to the trigger.
- Touch targets of at least 44 by 44 CSS px for primary controls.
- Labels, error associations, status announcements, and non-color state cues.
- No content lost at 200% zoom, text reflow, or the required mobile widths.
- Forced-colors focus and boundaries remain visible.
- Reduced motion removes non-essential transitions.
- Charts include captions, direct labels, or equivalent tabular/text summaries.

## Contribution checklist

Before adding or changing a user-facing pattern:

1. Confirm the route’s user goal and the one most important next action.
2. Reuse semantic tokens and a shared primitive before adding a local variant.
3. Implement loading, empty, success, failure, disabled, and permission states.
4. Preserve provenance, ownership, version, and audit behavior in the interface.
5. Verify keyboard order, visible focus, accessible names, reduced motion, and
   320–1920 px reflow.
6. Add or update component tests and the route’s visual-QA row.
7. Run format, lint, typecheck, unit tests, production build, and relevant E2E
   journeys. Record any unavailable gate rather than implying it passed.
8. Do not add a dependency for a complete-only enhancement. For a dependency
   that materially improves a core workflow, document bundle, privacy,
   maintenance, accessibility, and fallback impact first.
