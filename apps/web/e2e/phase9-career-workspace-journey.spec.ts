import { randomUUID } from "node:crypto";

import {
  expect,
  test,
  type APIRequestContext,
  type Locator,
  type Page,
} from "@playwright/test";

type MailpitSearchResponse = { messages?: Array<{ ID?: string }> };

const mailpitUrl = process.env.PLAYWRIGHT_MAILPIT_URL;
const password = `${randomUUID()}-aA1!`;
const actionTimeout = 7_500;
const workerTimeout = 120_000;

const canonicalScoreDisclaimer =
  "CareerOS scores are internal readiness measurements. They are not scores provided by an employer or applicant tracking system and do not guarantee interviews or employment outcomes.";
const nonCausalInterpretation =
  "These analytics describe correlations and observed patterns only. They do not establish causation, predict hiring decisions, or promise career outcomes.";
const promotionReadinessDisclaimer =
  "Promotion Readiness summarizes CareerOS preparation signals from current eligible evidence and owner-maintained records. It is not an employer decision, hiring probability, promotion guarantee, or assessment of job-market value.";

const fictional = {
  annualRefresh: "Fictional annual evidence-backed resume refresh",
  applicationSource: "Fictional Phase 9 referral",
  company: "Fictional Career Workspace Labs",
  contact: "Fictional Career Guide",
  development: "Fictional discovery practice plan",
  evidenceStatement:
    "User states that they conducted customer discovery interviews and synthesized the findings into a product recommendation.",
  evidenceTitle: "Fictional customer discovery source note",
  employer: "Fictional Products Limited",
  goal: "Fictional discovery leadership goal",
  interaction:
    "Fictional local record: the user states that a career conversation already happened.",
  jobTitle: "Fictional Product Discovery Lead",
  milestone: "Fictional interview synthesis milestone",
  note: "Fictional private note: prepare an evidence-grounded interview example.",
  organization: "Fictional Career Network",
  referral:
    "Fictional local referral plan recorded by the user; no request was sent.",
  reminder: "Fictional local follow-up review",
  resumeTitle: "Fictional Product Discovery Resume",
  review: "Fictional quarterly career review",
  session: "Fictional behavioral interview practice",
  skill: "Customer discovery",
  story: "Fictional customer discovery STAR story",
  template: "Fictional reviewed introduction",
  templateBody:
    "Hello. This is fictional text saved for manual review only; CareerOS must not send it.",
};

async function expectActionable(locator: Locator) {
  await expect(locator).toBeVisible({ timeout: actionTimeout });
  await expect(locator).toBeEnabled({ timeout: actionTimeout });
}

async function activate(locator: Locator, keyboard: boolean) {
  await expectActionable(locator);
  if (keyboard) {
    await locator.focus({ timeout: actionTimeout });
    await expect(locator).toBeFocused({ timeout: actionTimeout });
    await locator.press("Enter", { timeout: actionTimeout });
    return;
  }
  await locator.click({ timeout: actionTimeout });
}

async function fill(locator: Locator, value: string) {
  await expectActionable(locator);
  await locator.fill(value, { timeout: actionTimeout });
}

async function select(locator: Locator, value: string | { index: number }) {
  await expectActionable(locator);
  await locator.selectOption(value, { timeout: actionTimeout });
}

async function attest(locator: Locator, keyboard: boolean) {
  await expectActionable(locator);
  if (!(await locator.isChecked())) {
    if (keyboard) {
      await locator.focus({ timeout: actionTimeout });
      await expect(locator).toBeFocused({ timeout: actionTimeout });
      await locator.press("Space", { timeout: actionTimeout });
    } else {
      await locator.check({ timeout: actionTimeout });
    }
  }
  await expect(locator).toBeChecked({ timeout: actionTimeout });
}

function requireMailpitUrl(): string {
  if (!mailpitUrl) {
    throw new Error(
      "PLAYWRIGHT_MAILPIT_URL is required for the full-stack Phase 9 career-workspace journey.",
    );
  }
  return mailpitUrl.replace(/\/$/, "");
}

async function findVerificationLink(
  request: APIRequestContext,
  email: string,
): Promise<string | undefined> {
  const response = await request.get(`${requireMailpitUrl()}/api/v1/search`, {
    params: { query: `to:${email}` },
  });
  if (!response.ok()) return undefined;
  const body = (await response.json()) as MailpitSearchResponse;
  const messageId = body.messages?.[0]?.ID;
  if (!messageId) return undefined;
  const message = await request.get(
    `${requireMailpitUrl()}/view/${encodeURIComponent(messageId)}.txt`,
  );
  if (!message.ok()) return undefined;
  return (await message.text()).match(
    /https?:\/\/[^\s<>]+\/verify-email#token=[A-Za-z0-9._~-]+/,
  )?.[0];
}

async function verificationLink(
  request: APIRequestContext,
  email: string,
): Promise<string> {
  let link: string | undefined;
  await expect
    .poll(
      async () => {
        link = await findVerificationLink(request, email);
        return Boolean(link);
      },
      {
        message: "verification email to arrive in the isolated Mailpit inbox",
        timeout: 20_000,
      },
    )
    .toBe(true);
  return link!;
}

async function registerAndSignIn(
  page: Page,
  request: APIRequestContext,
  email: string,
  keyboard: boolean,
) {
  await page.goto("/register");
  await fill(page.getByLabel("Name"), "Phase 9 Career Workspace E2E");
  await fill(page.getByLabel("Email address"), email);
  await fill(page.getByLabel("Password", { exact: true }), password);
  await activate(
    page.getByRole("button", { name: "Create account" }),
    keyboard,
  );
  await expect(
    page.getByRole("heading", { name: "Check your email" }),
  ).toBeVisible();

  const link = new URL(await verificationLink(request, email));
  await page.goto(`${link.pathname}${link.hash}`);
  await expect(
    page.getByRole("heading", { name: "Email verified" }),
  ).toBeVisible();
  await activate(
    page.getByRole("link", { name: "Continue to sign in" }),
    keyboard,
  );
  await fill(page.getByLabel("Email address"), email);
  await fill(page.getByLabel("Password", { exact: true }), password);
  await activate(
    page.getByRole("button", { name: "Sign in", exact: true }),
    keyboard,
  );
  await expect(page).toHaveURL(/\/(dashboard|onboarding)$/);
}

function dateOffset(days: number): string {
  const value = new Date();
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}

function localDateTimeOffset(minutes: number): string {
  const value = new Date(Date.now() + minutes * 60_000);
  const localValue = new Date(
    value.getTime() - value.getTimezoneOffset() * 60_000,
  );
  return localValue.toISOString().slice(0, 16);
}

async function createGroundedApplication(
  page: Page,
  keyboard: boolean,
): Promise<string> {
  await page.goto("/career-profile");
  await expect(
    page.getByRole("heading", { name: "Career Profile" }),
  ).toBeVisible();
  await activate(page.getByRole("button", { name: "Add skill" }), keyboard);
  await fill(page.getByLabel("Skill name"), fictional.skill);
  await select(page.getByLabel("Proficiency (optional)"), "advanced");
  await activate(page.getByRole("button", { name: "Save skill" }), keyboard);
  await expect(page.getByText("Skill saved.")).toBeVisible();

  await activate(
    page.getByRole("button", { name: "Add experience" }),
    keyboard,
  );
  await fill(page.getByLabel("Employer"), fictional.employer);
  await fill(page.getByLabel("Official title"), "Product Researcher");
  await fill(page.getByLabel("Start month"), "2024-04");
  await attest(
    page.getByRole("checkbox", { name: fictional.skill, exact: true }),
    keyboard,
  );
  await activate(
    page.getByRole("button", { name: "Add experience" }).last(),
    keyboard,
  );
  await expect(
    page.getByText("Experience added to your career profile."),
  ).toBeVisible();

  await page.goto("/evidence");
  await expect(
    page.getByRole("heading", { name: "Evidence Vault", exact: true }),
  ).toBeVisible();
  await activate(page.getByRole("button", { name: "Add evidence" }), keyboard);
  await fill(page.getByLabel("Evidence title"), fictional.evidenceTitle);
  await select(page.getByLabel("Evidence type"), "user_confirmed_achievement");
  await fill(page.getByLabel("Description"), fictional.evidenceStatement);
  await attest(
    page.getByLabel(`Product Researcher at ${fictional.employer}`),
    keyboard,
  );
  await attest(
    page.getByRole("checkbox", { name: fictional.skill, exact: true }),
    keyboard,
  );
  await activate(page.getByRole("button", { name: "Save evidence" }), keyboard);
  await expect(
    page.getByText("Evidence saved.", { exact: false }),
  ).toBeVisible();

  const evidenceReview = page.getByRole("link", { name: /^Review/ });
  await expect(evidenceReview).toHaveCount(1);
  const evidenceHref = await evidenceReview.getAttribute("href");
  const evidenceId = evidenceHref?.split("/").filter(Boolean).at(-1);
  if (!evidenceId || evidenceId === "evidence") {
    throw new Error("The evidence review link did not expose an ID.");
  }
  await activate(evidenceReview, keyboard);
  await expect(page).toHaveURL(new RegExp(`/evidence/${evidenceId}$`));
  await expect(
    page.getByRole("heading", {
      name: fictional.evidenceTitle,
      exact: true,
    }),
  ).toBeVisible();
  await activate(
    page.getByRole("button", { name: "Confirm evidence" }),
    keyboard,
  );
  await expect(
    page.getByText("Evidence confirmed.", { exact: false }),
  ).toBeVisible();

  await page.goto("/job-match");
  await expect(
    page.getByRole("heading", { name: "Application readiness" }),
  ).toBeVisible();
  await fill(page.getByLabel("Job title"), fictional.jobTitle);
  await fill(page.getByLabel("Company"), fictional.company);
  await fill(page.getByLabel("Location"), "Remote");
  await select(page.getByLabel("Work model"), "remote");
  await select(page.getByLabel("Employment type"), "full_time");
  await fill(
    page.getByLabel("Job description"),
    [
      `Title: ${fictional.jobTitle}`,
      `Company: ${fictional.company}`,
      "Location: Remote",
      "Requirements:",
      "- Must have conducted customer discovery interviews and synthesized findings into a product recommendation.",
      "- Collaborate with engineering and design on product experiments.",
      "- Preferred experience with product analytics.",
    ].join("\n"),
  );
  await activate(page.getByRole("button", { name: "Save job" }), keyboard);
  await expect(page.getByRole("status")).toContainText(
    `${fictional.jobTitle} saved for matching.`,
  );
  await activate(page.getByRole("button", { name: "Analyze match" }), keyboard);
  await expect(
    page.getByRole("table", {
      name: "Requirement-by-requirement job match evidence matrix",
    }),
  ).toBeVisible();
  await expect(page.getByText(fictional.evidenceTitle).first()).toBeVisible();

  await page.goto("/resume-builder");
  await expect(
    page.getByRole("heading", { name: "Evidence-backed resume studio" }),
  ).toBeVisible();
  await fill(page.getByLabel("Resume title"), fictional.resumeTitle);
  await fill(page.getByLabel("Target role"), fictional.jobTitle);
  await select(page.getByLabel("Template"), "standard_professional");
  await activate(page.getByRole("button", { name: "Create" }), keyboard);
  await expect(
    page
      .getByRole("status")
      .getByText("Resume created from eligible Career Record evidence."),
  ).toBeVisible();
  await expect(
    page.getByRole("listitem").filter({
      hasText: fictional.evidenceStatement,
    }),
  ).toBeVisible();

  await page.goto("/applications");
  await expect(
    page.getByRole("heading", {
      name: "Keep every application traceable",
    }),
  ).toBeVisible();
  const createPanel = page.locator("details").filter({
    has: page.getByText("Add an application", { exact: true }),
  });
  await expect(createPanel).toHaveCount(1);
  await activate(
    createPanel.getByText("Add an application", { exact: true }),
    keyboard,
  );
  await expect(createPanel).toHaveAttribute("open", "");
  await select(
    createPanel.getByRole("combobox", { name: "Saved job", exact: true }),
    { index: 0 },
  );
  await select(
    createPanel.getByRole("combobox", { name: "Resume", exact: true }),
    { index: 0 },
  );
  await expect(
    createPanel.getByLabel("Immutable resume version"),
  ).toBeEnabled();
  await select(createPanel.getByLabel("Immutable resume version"), {
    index: 0,
  });
  await select(createPanel.getByLabel("Initial stage"), "applied");
  await fill(createPanel.getByLabel("Application deadline"), dateOffset(30));
  await fill(createPanel.getByLabel("Follow-up date"), dateOffset(14));
  await fill(
    createPanel.getByLabel("Application source"),
    fictional.applicationSource,
  );
  await fill(createPanel.getByLabel("Industry"), "Fictional product software");
  await activate(
    createPanel.getByRole("button", { name: "Add application" }),
    keyboard,
  );
  await expect(page.getByRole("status").first()).toContainText(
    `${fictional.jobTitle} added to your workspace.`,
  );
  return evidenceId;
}

async function exerciseInterviewPrep(page: Page, keyboard: boolean) {
  await page.goto("/interview-prep");
  await expect(
    page.getByRole("heading", {
      name: "Defend every important resume claim",
    }),
  ).toBeVisible();
  await select(page.getByLabel("Application context"), { index: 1 });
  const defenseMap = page.getByRole("heading", {
    name: "Resume Defense Map",
  });
  await expect(defenseMap).toBeVisible();
  await expect(
    page.getByText(fictional.evidenceStatement).first(),
  ).toBeVisible();

  await activate(
    page.getByRole("button", { name: "Add STAR story" }),
    keyboard,
  );
  const storyForm = page.locator("form").filter({
    has: page.getByRole("heading", {
      name: "Add an evidence-linked STAR story",
    }),
  });
  await fill(storyForm.getByLabel("Story title"), fictional.story);
  await select(storyForm.getByLabel("Confidence"), "4");
  await select(storyForm.getByLabel("Story status"), "ready");
  await fill(
    storyForm.getByRole("textbox", { name: "Situation", exact: true }),
    "The user states that a fictional product team needed clearer customer evidence.",
  );
  await fill(
    storyForm.getByRole("textbox", { name: "Task", exact: true }),
    "The user states that they were responsible for organizing customer discovery.",
  );
  await fill(
    storyForm.getByRole("textbox", { name: "Action", exact: true }),
    "The user states that they conducted interviews and synthesized the findings.",
  );
  await fill(
    storyForm.getByRole("textbox", { name: "Result", exact: true }),
    "The user states that the synthesis informed a product recommendation.",
  );
  await fill(
    storyForm.getByRole("textbox", {
      name: "Personal contribution",
      exact: true,
    }),
    "The user states that they personally conducted the interviews and prepared the synthesis.",
  );
  await fill(
    storyForm.getByLabel("Likely follow-up questions"),
    "How did you synthesize the interview findings?",
  );
  await attest(
    storyForm.getByRole("checkbox", {
      name: fictional.evidenceStatement,
      exact: false,
    }),
    keyboard,
  );
  await activate(
    storyForm.getByRole("button", { name: "Save grounded story" }),
    keyboard,
  );
  await expect(
    page.getByText(/saved with exact claim and evidence revision/),
  ).toBeVisible();

  await activate(
    page.getByRole("button", { name: "Create session" }),
    keyboard,
  );
  const sessionForm = page.locator("form").filter({
    has: page.getByLabel("Session title"),
  });
  await fill(sessionForm.getByLabel("Session title"), fictional.session);
  await select(sessionForm.getByLabel("Session type"), "behavioral");
  await fill(
    sessionForm.getByLabel("Scheduled time (optional)"),
    localDateTimeOffset(120),
  );
  await activate(
    sessionForm.getByRole("button", { name: "Create private session" }),
    keyboard,
  );
  await expect(
    page.getByText(/created from an immutable bounded context/),
  ).toBeVisible();

  const storyCard = page.locator("li").filter({ hasText: fictional.story });
  await activate(
    storyCard.getByRole("link", { name: "Review story" }),
    keyboard,
  );
  const provenance = page.getByRole("region", {
    name: "Machine-checkable provenance",
  });
  await expect(provenance).toBeVisible();
  const evidencePin = provenance.getByRole("listitem").filter({
    hasText: fictional.evidenceStatement,
  });
  await expect(evidencePin).toBeVisible();
  await expect(evidencePin.getByText(/Revision \d+/)).toBeVisible();
  await activate(
    page.locator("#main-content").getByRole("link", { name: "Interview Prep" }),
    keyboard,
  );

  const sessionCard = page.locator("li").filter({ hasText: fictional.session });
  await activate(
    sessionCard.getByRole("link", { name: "Open session" }),
    keyboard,
  );
  await expect(
    page.getByRole("heading", { name: fictional.session }),
  ).toBeVisible();

  await activate(page.getByRole("tab", { name: /^Questions/ }), keyboard);
  await expect(page.getByText("Grounded question bank")).toBeVisible();
  await activate(
    page.getByRole("button", { name: "Generate grounded questions" }),
    keyboard,
  );
  await expect(
    page.getByText(
      /grounded questions generated from the immutable session context/,
    ),
  ).toBeVisible();
  await expect(page.getByText("Evidence current").first()).toBeVisible();

  await activate(page.getByRole("tab", { name: /^Private notes/ }), keyboard);
  const noteForm = page.locator("form").filter({
    has: page.getByRole("heading", { name: "Add a private note" }),
  });
  await select(noteForm.getByLabel("Note type"), "reflection");
  await fill(
    noteForm.getByRole("textbox", { name: "Note", exact: true }),
    fictional.note,
  );
  await activate(
    noteForm.getByRole("button", { name: "Save private note" }),
    keyboard,
  );
  await expect(page.getByText("Private note saved.")).toBeVisible();
  await expect(page.getByLabel("Private content").first()).toHaveValue(
    fictional.note,
  );

  await activate(
    page.getByRole("tab", { name: /^Follow-up drafts/ }),
    keyboard,
  );
  await expect(
    page.getByText("Draft only — no sending capability"),
  ).toBeVisible();
  await attest(
    page.getByRole("checkbox", {
      name: fictional.evidenceStatement,
      exact: false,
    }),
    keyboard,
  );
  await activate(
    page.getByRole("button", { name: "Create grounded review draft" }),
    keyboard,
  );
  await expect(
    page.getByText(
      "A grounded draft was created for your review. CareerOS did not send it.",
    ),
  ).toBeVisible();
  await expect(page.getByText("Review required")).toBeVisible();
  await expect(page.getByText("Not sent")).toBeVisible();
  await expect(
    page.getByRole("button", { name: /\b(send|submit)\b/i }),
  ).toHaveCount(0);
}

async function exerciseNetworking(page: Page, keyboard: boolean) {
  await page.goto("/networking");
  await expect(
    page.getByRole("heading", {
      name: "A private, consent-based relationship workspace",
    }),
  ).toBeVisible();
  await expect(
    page.getByText("No external delivery or scraping"),
  ).toBeVisible();

  await activate(page.getByRole("tab", { name: /^Organizations/ }), keyboard);
  await activate(
    page.getByRole("button", { name: "Add organization" }),
    keyboard,
  );
  const organizationForm = page
    .locator("form")
    .filter({
      has: page.getByLabel("Website (stored only)"),
    })
    .first();
  await fill(organizationForm.getByLabel("Name"), fictional.organization);
  await fill(
    organizationForm.getByLabel("Industry"),
    "Fictional career services",
  );
  await fill(organizationForm.getByLabel("Location"), "Remote");
  await fill(
    organizationForm.getByLabel("Tags (comma separated)"),
    "fictional",
  );
  await activate(
    organizationForm.getByRole("button", { name: "Save organization" }),
    keyboard,
  );
  await expect(
    page.getByText(`${fictional.organization} saved.`),
  ).toBeVisible();

  await activate(
    page.getByRole("tab", { name: /^Reviewed templates/ }),
    keyboard,
  );
  await activate(
    page.getByRole("button", { name: "Add reviewed template" }),
    keyboard,
  );
  const templateForm = page.locator("form").filter({
    has: page.getByLabel("Template name"),
  });
  await fill(templateForm.getByLabel("Template name"), fictional.template);
  await select(templateForm.getByLabel("Kind"), "introduction");
  await fill(
    templateForm.getByLabel("Local template text"),
    fictional.templateBody,
  );
  await attest(
    templateForm.getByRole("checkbox", {
      name: "I reviewed this text and understand CareerOS will not send it",
    }),
    keyboard,
  );
  await activate(
    templateForm.getByRole("button", { name: "Save reviewed template" }),
    keyboard,
  );
  await expect(
    page.getByText(`${fictional.template} saved for manual review and use.`),
  ).toBeVisible();

  await activate(page.getByRole("tab", { name: /^Contacts/ }), keyboard);
  await activate(page.getByRole("button", { name: "Add contact" }), keyboard);
  const contactForm = page.locator("form").filter({
    has: page.getByRole("heading", { name: "Add a private contact" }),
  });
  await fill(contactForm.getByLabel("Name"), fictional.contact);
  await fill(contactForm.getByLabel("Role"), "Fictional career advisor");
  await select(contactForm.getByLabel("Organization"), { index: 1 });
  await fill(
    contactForm.getByLabel("Email"),
    "fictional.contact@e2e.invalid.example.com",
  );
  await fill(contactForm.getByLabel("Location"), "Remote");
  await fill(
    contactForm.getByLabel("Tags (comma separated)"),
    "fictional, private",
  );
  await attest(
    contactForm.getByRole("checkbox", {
      name: "Collection consent is attested",
    }),
    keyboard,
  );
  await attest(
    contactForm.getByRole("checkbox", {
      name: "Storage consent is attested",
    }),
    keyboard,
  );
  await expect(
    contactForm.getByRole("checkbox", {
      name: "Outreach consent is attested",
    }),
  ).not.toBeChecked();
  await activate(
    contactForm.getByRole("button", { name: "Save consented contact" }),
    keyboard,
  );
  await expect(
    page.getByText(
      /saved with separate collection, storage, and outreach consent state/,
    ),
  ).toBeVisible();

  const contactCard = page.locator("li").filter({ hasText: fictional.contact });
  await expect(contactCard.getByText("Outreach blocked")).toBeVisible();
  await activate(
    contactCard.getByRole("link", { name: "Open private record" }),
    keyboard,
  );
  await expect(
    page.getByRole("heading", { name: fictional.contact }),
  ).toBeVisible();

  await activate(page.getByRole("tab", { name: /^Consent history/ }), keyboard);
  const grantForm = page.locator("form").filter({
    has: page.getByRole("heading", { name: "Grant consent" }),
  });
  await select(grantForm.getByLabel("Purpose"), "outreach");
  await activate(
    grantForm.getByRole("button", { name: "Record grant" }),
    keyboard,
  );
  await expect(
    page.getByText(
      "Outreach consent granted and recorded in the append-only history.",
    ),
  ).toBeVisible();
  await expect(page.getByText("Granted", { exact: true }).last()).toBeVisible();

  await activate(page.getByRole("tab", { name: /^Notes/ }), keyboard);
  await fill(
    page.getByRole("textbox", { name: "Private note", exact: true }),
    fictional.note,
  );
  await activate(
    page.getByRole("button", { name: "Save private note" }),
    keyboard,
  );
  await expect(
    page.getByText("Private relationship note saved."),
  ).toBeVisible();
  await expect(page.getByText(fictional.note)).toBeVisible();

  await activate(page.getByRole("tab", { name: /^Interactions/ }), keyboard);
  await fill(page.getByLabel("When it happened"), localDateTimeOffset(-60));
  await select(page.getByLabel("Reviewed template reference (optional)"), {
    index: 1,
  });
  await fill(
    page.getByLabel("Private summary of what already happened"),
    fictional.interaction,
  );
  await activate(
    page.getByRole("button", { name: "Record local history" }),
    keyboard,
  );
  await expect(
    page.getByText(
      "Interaction recorded as local history only. CareerOS did not send anything.",
    ),
  ).toBeVisible();
  await expect(page.getByText("Recorded Only", { exact: true })).toBeVisible();

  await activate(page.getByRole("tab", { name: /^Referrals/ }), keyboard);
  const referralsPanel = page.getByRole("tabpanel", { name: /^Referrals/ });
  await select(
    referralsPanel.getByRole("combobox", {
      name: "Application",
      exact: true,
    }),
    { index: 1 },
  );
  await select(
    referralsPanel
      .getByRole("combobox", { name: "Status", exact: true })
      .first(),
    "planned",
  );
  await fill(
    referralsPanel.getByRole("textbox", {
      name: "Private context (optional)",
      exact: true,
    }),
    fictional.referral,
  );
  await activate(
    page.getByRole("button", { name: "Record local referral" }),
    keyboard,
  );
  await expect(
    page.getByText("Referral state recorded locally. No request was sent."),
  ).toBeVisible();
  await expect(page.getByText(fictional.referral)).toBeVisible();

  await activate(page.getByRole("tab", { name: /^Local reminders/ }), keyboard);
  await fill(page.getByLabel("Reminder title"), fictional.reminder);
  await fill(page.getByLabel("Due time"), localDateTimeOffset(-2));
  await activate(
    page.getByRole("button", { name: "Create local reminder" }),
    keyboard,
  );
  await expect(
    page.getByText(
      "Local reminder created. It will never email, message, or push this contact.",
    ),
  ).toBeVisible();
  const reminderRecord = page.locator("form").filter({
    has: page.getByLabel("Title", { exact: true }),
  });
  await expect(reminderRecord.getByLabel("Title", { exact: true })).toHaveValue(
    fictional.reminder,
  );

  await expect
    .poll(
      async () => {
        await page.reload();
        await expect(
          page.getByRole("heading", { name: fictional.contact }),
        ).toBeVisible();
        await activate(
          page.getByRole("tab", { name: /^Local reminders/ }),
          keyboard,
        );
        const processed = page
          .getByRole("tabpanel", { name: /^Local reminders/ })
          .getByText("Queue: Processed", { exact: true });
        try {
          await processed.waitFor({ state: "visible", timeout: 5_000 });
          return true;
        } catch {
          return false;
        }
      },
      {
        intervals: [2_000, 4_000, 6_000, 8_000],
        message:
          "the durable local-only reminder worker to acknowledge the occurrence",
        timeout: workerTimeout,
      },
    )
    .toBe(true);
  await expect(
    page
      .getByRole("tabpanel", { name: /^Local reminders/ })
      .getByText("No delivery action exists."),
  ).toBeVisible();

  // The reminder worker updates the contact version in the same transaction
  // that acknowledges the occurrence. The execution read can observe that
  // commit after the page's parallel contact read, so reload once after the
  // durable worker state is visible before issuing an optimistic write.
  await page.reload();
  await expect(
    page.getByRole("heading", { name: fictional.contact }),
  ).toBeVisible();
  await activate(page.getByRole("tab", { name: /^Consent history/ }), keyboard);
  const withdrawForm = page.locator("form").filter({
    has: page.getByRole("heading", { name: "Withdraw consent" }),
  });
  await select(withdrawForm.getByLabel("Purpose"), "outreach");
  await activate(
    withdrawForm.getByRole("button", { name: "Record withdrawal" }),
    keyboard,
  );
  await expect(
    page.getByText(
      "Outreach consent withdrawn and recorded in the append-only history.",
    ),
  ).toBeVisible();
  await expect(
    page
      .getByRole("tabpanel", { name: /^Consent history/ })
      .getByRole("list")
      .getByText("Withdrawn", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: /\b(send|scrape|import|email|message)\b/i,
    }),
  ).toHaveCount(0);
}

async function exerciseCareerGrowth(
  page: Page,
  keyboard: boolean,
  evidenceId: string,
) {
  await page.goto("/career-growth");
  await expect(
    page.getByRole("heading", {
      name: "Turn career maintenance into a steady practice",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Achievement and promotion preparation",
    }),
  ).toBeVisible();
  await expect(page.getByTestId("promotion-readiness-disclaimer")).toHaveText(
    promotionReadinessDisclaimer,
  );
  await expect(
    page.getByRole("table", {
      name: "Promotion preparation checks, evidence state, and next action",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Achievement history" }),
  ).toBeVisible();
  const achievementHistory = page
    .getByRole("heading", { name: "Achievement history" })
    .locator("..");
  await expect(
    achievementHistory.getByRole("heading", {
      name: fictional.evidenceTitle,
    }),
  ).toBeVisible();
  await expect(
    achievementHistory.getByRole("link", { name: "Review exact evidence" }),
  ).toHaveAttribute("href", `/evidence/${evidenceId}`);
  await expect(
    page.getByRole("heading", { name: "Skill-evidence dashboard" }),
  ).toBeVisible();
  const skillEvidenceTable = page.getByRole("table", {
    name: "Documented skills and their eligible evidence coverage",
  });
  await expect(skillEvidenceTable).toBeVisible();
  await expect(
    skillEvidenceTable.getByRole("row", { name: new RegExp(fictional.skill) }),
  ).toContainText("1 eligible");

  const goalDetails = page.locator("details").filter({
    has: page.getByText("Add a career goal", { exact: true }),
  });
  await activate(
    goalDetails.getByText("Add a career goal", { exact: true }),
    keyboard,
  );
  await fill(goalDetails.getByLabel("Goal title"), fictional.goal);
  await fill(goalDetails.getByLabel("Target date"), dateOffset(90));
  await select(goalDetails.getByLabel("Status"), "active");
  await fill(
    goalDetails.getByLabel("Description"),
    "Fictional user-authored goal for maintaining customer discovery practice.",
  );
  await fill(goalDetails.getByLabel("Evidence IDs"), evidenceId);
  await activate(
    goalDetails.getByRole("button", { name: "Add goal" }),
    keyboard,
  );
  await expect(
    page.getByText(`${fictional.goal} added as a career goal.`),
  ).toBeVisible();

  const goalCard = page
    .getByRole("article")
    .filter({ has: page.getByRole("heading", { name: fictional.goal }) });
  const milestoneDetails = goalCard.locator("details").filter({
    has: page.getByText("Add milestone", { exact: true }),
  });
  await activate(milestoneDetails.locator("summary"), keyboard);
  await fill(milestoneDetails.getByLabel("Title"), fictional.milestone);
  await select(milestoneDetails.getByLabel("Status"), "in_progress");
  await fill(milestoneDetails.getByLabel("Target date"), dateOffset(30));
  await fill(milestoneDetails.getByLabel("Evidence IDs"), evidenceId);
  await activate(
    milestoneDetails.getByRole("button", { name: "Add milestone" }),
    keyboard,
  );
  await expect(
    page.getByText(`${fictional.milestone} added as a milestone.`),
  ).toBeVisible();

  const developmentDetails = page.locator("details").filter({
    has: page.getByText("Add a development plan item", { exact: true }),
  });
  await activate(
    developmentDetails.getByText("Add a development plan item", {
      exact: true,
    }),
    keyboard,
  );
  await fill(developmentDetails.getByLabel("Title"), fictional.development);
  await select(developmentDetails.getByLabel("Kind"), "learning");
  await select(developmentDetails.getByLabel("Status"), "in_progress");
  await fill(developmentDetails.getByLabel("Target date"), dateOffset(45));
  await fill(
    developmentDetails.getByLabel("Description"),
    "Fictional user-authored plan to practice customer discovery synthesis.",
  );
  await fill(developmentDetails.getByLabel("Evidence IDs"), evidenceId);
  await activate(
    developmentDetails.getByRole("button", { name: "Add plan item" }),
    keyboard,
  );
  await expect(
    page.getByText(`${fictional.development} added to your development plan.`),
  ).toBeVisible();

  await fill(developmentDetails.getByLabel("Title"), fictional.annualRefresh);
  await select(developmentDetails.getByLabel("Kind"), "annual_resume_refresh");
  await select(developmentDetails.getByLabel("Status"), "completed");
  await fill(developmentDetails.getByLabel("Target date"), dateOffset(365));
  await fill(
    developmentDetails.getByLabel("Description"),
    "Fictional owner-authored annual workflow that refreshes a resume only from current eligible evidence.",
  );
  await fill(developmentDetails.getByLabel("Evidence IDs"), evidenceId);
  await activate(
    developmentDetails.getByRole("button", { name: "Add plan item" }),
    keyboard,
  );
  await expect(
    page.getByText(
      `${fictional.annualRefresh} added to your development plan.`,
    ),
  ).toBeVisible();
  const annualRefreshWorkflow = page
    .getByRole("heading", { name: "Annual resume refresh workflow" })
    .locator("..");
  await expect(
    annualRefreshWorkflow.getByText(fictional.annualRefresh, { exact: true }),
  ).toBeVisible();
  const annualRefreshItem = annualRefreshWorkflow
    .getByRole("listitem")
    .filter({ hasText: fictional.annualRefresh });
  await expect(annualRefreshItem).toContainText("Completed");
  await expect(annualRefreshItem).toContainText("1 eligible evidence link(s)");

  const reviewDetails = page.locator("details").filter({
    has: page.getByText("Start a career review", { exact: true }),
  });
  await activate(
    reviewDetails.getByText("Start a career review", { exact: true }),
    keyboard,
  );
  await select(reviewDetails.getByLabel("Cadence"), "quarterly");
  await fill(reviewDetails.getByLabel("Period start"), dateOffset(-60));
  await fill(reviewDetails.getByLabel("Period end"), dateOffset(0));
  await fill(reviewDetails.getByLabel("Review title"), fictional.review);
  await fill(
    reviewDetails.getByLabel("Summary"),
    "The user records a fictional quarterly review of customer discovery practice.",
  );
  await fill(
    reviewDetails.getByLabel("Achievements"),
    "The user states that they completed customer discovery interviews.",
  );
  await fill(
    reviewDetails.getByLabel("Growth areas"),
    "The user wants to improve synthesis clarity.",
  );
  await fill(
    reviewDetails.getByLabel("Next focus"),
    "The user plans to practice concise evidence-grounded explanations.",
  );
  await fill(reviewDetails.getByLabel("Evidence IDs"), evidenceId);
  await activate(
    reviewDetails.getByRole("button", { name: "Start draft review" }),
    keyboard,
  );
  await expect(
    page.getByText(`${fictional.review} started as a draft.`),
  ).toBeVisible();

  const reviewCard = page
    .getByRole("article")
    .filter({ has: page.getByRole("heading", { name: fictional.review }) });
  const revisionDetails = reviewCard.locator("details").filter({
    has: page.getByText("Create a new revision", { exact: true }),
  });
  await activate(
    revisionDetails.getByText("Create a new revision", { exact: true }),
    keyboard,
  );
  await fill(
    revisionDetails.getByLabel("Summary"),
    "The user revises the fictional quarterly review after checking the linked evidence.",
  );
  await fill(
    revisionDetails.getByLabel("Reason for this revision"),
    "Clarified the user-authored summary after evidence review.",
  );
  await activate(
    revisionDetails.getByRole("button", { name: "Review revision" }),
    keyboard,
  );
  const revisionDialog = page.getByRole("dialog", {
    name: "Create a new review revision?",
  });
  await activate(
    revisionDialog.getByRole("button", { name: "Create revision" }),
    keyboard,
  );
  await expect(
    page.getByText("Version 2 created without changing earlier versions."),
  ).toBeVisible();
  await expect(reviewCard.getByText("Version 2").first()).toBeVisible();

  await activate(
    reviewCard.getByRole("button", { name: "Finalize" }),
    keyboard,
  );
  const finalizeDialog = page.getByRole("dialog", {
    name: "Finalize this review version?",
  });
  await activate(
    finalizeDialog.getByRole("button", { name: "Finalize review" }),
    keyboard,
  );
  await expect(page.getByText(`${fictional.review} finalized.`)).toBeVisible();
  await expect(
    reviewCard.getByText("Finalized", { exact: true }).first(),
  ).toBeVisible();

  await activate(
    page.getByRole("button", { name: "Calculate Career Health" }),
    keyboard,
  );
  await expect(
    page.getByText(/Career Health (recalculated|checked; more data is needed)/),
  ).toBeVisible();
  await expect(page.getByTestId("career-health-disclaimer")).toHaveText(
    canonicalScoreDisclaimer,
  );
  await expect(page.locator("#career-health-score")).toHaveText(
    /Insufficient data|\d+\s*\/100/,
  );
  await expect(
    page.getByRole("table", {
      name: "Career Health component scores, weights, contributions, and explanations",
    }),
  ).toBeVisible();
}

async function exerciseAnalytics(page: Page, keyboard: boolean) {
  await page.goto("/analytics");
  await expect(
    page.getByRole("heading", { name: "Inspect observed career patterns" }),
  ).toBeVisible();
  await expect(page.getByTestId("non-causal-interpretation")).toHaveText(
    nonCausalInterpretation,
  );
  await expect(page.getByText("Overview report")).toBeVisible();
  await activate(
    page.getByRole("button", { name: "Refresh report" }),
    keyboard,
  );
  await expect(
    page.getByText(
      "Analytics refresh queued. This page will update automatically.",
    ),
  ).toBeVisible();
  await expect(
    page.getByText("Analytics refresh completed.", { exact: true }),
  ).toBeVisible({ timeout: workerTimeout });

  await expect(
    page.getByText("Current", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("table", {
      name: "Observed counts in the selected analytics window",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("table", {
      name: "Observed rates; small cohorts are suppressed for privacy",
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Suppressed (<5 observations)").first(),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Requirement coverage trend" }),
  ).toBeVisible();
  const coverageTrendTable = page.getByRole("table", {
    name: "Requirement coverage trend; small samples are suppressed",
  });
  await expect(coverageTrendTable).toBeVisible();
  await expect(coverageTrendTable.locator("tbody tr").first()).toBeVisible();
  await expect(
    coverageTrendTable.getByText("Suppressed (<5 observations)").first(),
  ).toBeVisible();

  await expect(
    page.getByRole("heading", {
      name: "Outcomes by immutable resume version",
    }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "These are observed correlations for the exact resume version pinned to each application. They cannot be interpreted as causal evidence.",
    ),
  ).toBeVisible();
  const resumeVersionOutcomeTable = page.getByRole("table", {
    name: "Observed outcomes segmented by exact immutable resume version",
  });
  await expect(resumeVersionOutcomeTable).toBeVisible();
  const resumeVersionRow = resumeVersionOutcomeTable.getByRole("row", {
    name: /Version 1/,
  });
  await expect(resumeVersionRow.getByRole("cell").first()).toHaveText("1");
  await expect(
    resumeVersionRow.getByText("Suppressed (<5 observations)").first(),
  ).toBeVisible();
  await expect(
    page.getByText("Recorded interpretation:", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(nonCausalInterpretation).last()).toBeVisible();

  const watermarkDetails = page.locator("details").filter({
    has: page.getByText(/Source completeness watermarks/),
  });
  await activate(
    watermarkDetails.getByText(/Source completeness watermarks/),
    keyboard,
  );
  await expect(
    watermarkDetails.getByRole("table", {
      name: "Source record counts and completeness watermark times",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: /\b(send|scrape|import|email|message)\b/i,
    }),
  ).toHaveCount(0);
}

test("an owner uses the four grounded Phase 9 career workspaces without external delivery", async ({
  page,
  request,
}, testInfo) => {
  test.setTimeout(360_000);
  page.setDefaultTimeout(actionTimeout);
  page.setDefaultNavigationTimeout(20_000);

  const keyboard = testInfo.project.name.includes("mobile");
  const email = `phase9-career-workspace-${randomUUID()}@e2e.invalid.example.com`;

  try {
    await test.step("register and verify a real owner account", async () => {
      await registerAndSignIn(page, request, email, keyboard);
    });

    let evidenceId = "";
    await test.step("create the minimum fictional, evidence-grounded application chain", async () => {
      evidenceId = await createGroundedApplication(page, keyboard);
    });

    await test.step("prepare grounded interviews and review an unsent follow-up", async () => {
      await exerciseInterviewPrep(page, keyboard);
    });

    await test.step("maintain consented networking records and process a local-only reminder", async () => {
      await exerciseNetworking(page, keyboard);
    });

    await test.step("maintain goals, plans, immutable reviews, and transparent Career Health", async () => {
      await exerciseCareerGrowth(page, keyboard, evidenceId);
    });

    await test.step("refresh and inspect non-causal, privacy-suppressed analytics", async () => {
      await exerciseAnalytics(page, keyboard);
    });
  } finally {
    await request
      .delete(`${requireMailpitUrl()}/api/v1/search`, {
        params: { query: `to:${email}` },
      })
      .catch(() => undefined);
  }
});
