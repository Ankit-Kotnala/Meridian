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
const actionTimeout = 5_000;

async function expectActionable(locator: Locator) {
  await expect(locator).toBeVisible({ timeout: actionTimeout });
  await expect(locator).toBeEnabled({ timeout: actionTimeout });
}

async function clickWhenReady(locator: Locator) {
  await expectActionable(locator);
  await locator.click({ timeout: actionTimeout });
}

async function fillWhenReady(locator: Locator, value: string) {
  await expectActionable(locator);
  await locator.fill(value, { timeout: actionTimeout });
}

async function selectWhenReady(
  locator: Locator,
  value: string | { index: number },
) {
  await expectActionable(locator);
  await locator.selectOption(value, { timeout: actionTimeout });
}

async function checkWhenReady(locator: Locator) {
  await expectActionable(locator);
  await locator.check({ timeout: actionTimeout });
}

async function uncheckWhenReady(locator: Locator) {
  await expectActionable(locator);
  await locator.uncheck({ timeout: actionTimeout });
}

async function focusWhenReady(locator: Locator) {
  await expectActionable(locator);
  await locator.focus({ timeout: actionTimeout });
  await expect(locator).toBeFocused({ timeout: actionTimeout });
}

function requireMailpitUrl(): string {
  if (!mailpitUrl) {
    throw new Error(
      "PLAYWRIGHT_MAILPIT_URL is required for the full-stack application-workspace journey.",
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
        timeout: 15_000,
      },
    )
    .toBe(true);
  return link!;
}

async function registerAndSignIn(
  page: Page,
  request: APIRequestContext,
  email: string,
) {
  await page.goto("/register");
  await fillWhenReady(page.getByLabel("Name"), "Application Workspace E2E");
  await fillWhenReady(page.getByLabel("Email address"), email);
  await fillWhenReady(page.getByLabel("Password", { exact: true }), password);
  await clickWhenReady(page.getByRole("button", { name: "Create account" }));
  await expect(
    page.getByRole("heading", { name: "Check your email" }),
  ).toBeVisible();

  const link = new URL(await verificationLink(request, email));
  await page.goto(`${link.pathname}${link.hash}`);
  await expect(
    page.getByRole("heading", { name: "Email verified" }),
  ).toBeVisible();
  await clickWhenReady(page.getByRole("link", { name: "Continue to sign in" }));
  await fillWhenReady(page.getByLabel("Email address"), email);
  await fillWhenReady(page.getByLabel("Password", { exact: true }), password);
  await clickWhenReady(
    page.getByRole("button", { name: "Sign in", exact: true }),
  );
  await expect(page).toHaveURL(/\/(dashboard|onboarding)$/);
}

function dateInCurrentMonth(day: number): string {
  return `${new Date().toISOString().slice(0, 7)}-${String(day).padStart(2, "0")}`;
}

test("a user tracks a grounded application and generates a consistent application pack", async ({
  page,
  request,
}, testInfo) => {
  test.setTimeout(180_000);
  page.setDefaultTimeout(actionTimeout);
  page.setDefaultNavigationTimeout(15_000);

  const email = `application-workspace-${randomUUID()}@e2e.invalid.example.com`;
  const jobTitle = "Application Product Lead";
  const company = "Fictional Application Labs";
  const evidenceTitle = "Fictional discovery synthesis";
  const evidenceStatement =
    "User states that they conducted customer discovery interviews and synthesized research findings.";
  const resumeTitle = "Application Product Lead Resume";
  const applicationDeadline = dateInCurrentMonth(20);
  const followUpDate = dateInCurrentMonth(15);
  const taskDueDate = dateInCurrentMonth(18);

  try {
    await test.step("register and verify a real account", async () => {
      await registerAndSignIn(page, request, email);
    });

    if (testInfo.project.name.includes("mobile")) {
      await test.step("operate the mobile application workspace with the keyboard", async () => {
        await page.goto("/applications");
        await expect(
          page.getByRole("heading", {
            name: "Keep every application traceable",
          }),
        ).toBeVisible();

        const tableView = page.getByRole("button", { name: "Table" });
        await focusWhenReady(tableView);
        await page.keyboard.press("Enter");
        await expect(page).toHaveURL(/[?&]view=table/);

        const addApplication = page.getByText("Add an application", {
          exact: true,
        });
        await focusWhenReady(addApplication);
        await page.keyboard.press("Enter");
        await expect(
          page.getByRole("heading", {
            name: "Complete the application sources",
          }),
        ).toBeVisible();

        const saveJob = page.getByRole("link", { name: "Save a job" });
        await focusWhenReady(saveJob);
        await page.keyboard.press("Enter");
        await expect(page).toHaveURL(/\/job-match$/);
      });
    }

    await test.step("create and confirm fictional Career Record evidence", async () => {
      await page.goto("/career-profile");
      await expect(
        page.getByRole("heading", { name: "Career profile" }),
      ).toBeVisible();

      await clickWhenReady(page.getByRole("button", { name: "Add skill" }));
      await fillWhenReady(page.getByLabel("Skill name"), "Product discovery");
      await selectWhenReady(
        page.getByLabel("Proficiency (optional)"),
        "advanced",
      );
      await clickWhenReady(page.getByRole("button", { name: "Save skill" }));
      await expect(page.getByText("Skill saved.")).toBeVisible();

      await clickWhenReady(
        page.getByRole("button", { name: "Add employment" }),
      );
      await fillWhenReady(
        page.getByLabel("Employer"),
        "Fictional Products Ltd",
      );
      await fillWhenReady(
        page.getByLabel("Official title"),
        "Product Researcher",
      );
      await fillWhenReady(page.getByLabel("Start month"), "2024-04");
      await checkWhenReady(
        page.getByRole("checkbox", {
          name: "Product discovery",
          exact: true,
        }),
      );
      await clickWhenReady(
        page.getByRole("button", { name: "Add experience" }),
      );
      await expect(
        page.getByText("Employment added to your career profile."),
      ).toBeVisible();

      await page.goto("/evidence");
      await expect(
        page.getByRole("heading", { name: "Evidence Vault", exact: true }),
      ).toBeVisible();
      await clickWhenReady(page.getByRole("button", { name: "Add evidence" }));
      await fillWhenReady(page.getByLabel("Evidence title"), evidenceTitle);
      await selectWhenReady(page.getByLabel("Evidence type"), "user_note");
      await fillWhenReady(page.getByLabel("Description"), evidenceStatement);
      await checkWhenReady(
        page.getByLabel("Product Researcher at Fictional Products Ltd"),
      );
      await checkWhenReady(
        page.getByRole("checkbox", {
          name: "Product discovery",
          exact: true,
        }),
      );
      await clickWhenReady(page.getByRole("button", { name: "Save evidence" }));
      await expect(
        page.getByText("Evidence saved.", { exact: false }),
      ).toBeVisible();

      const evidenceReview = page.getByRole("link", {
        name: /^Review(?: details)?$/,
      });
      await expect(evidenceReview).toHaveCount(1);
      await clickWhenReady(evidenceReview);
      await expect(
        page.getByRole("heading", { name: evidenceTitle, exact: true }),
      ).toBeVisible();
      await clickWhenReady(
        page.getByRole("button", { name: "Confirm evidence" }),
      );
      await expect(
        page.getByText("Evidence confirmed.", { exact: false }),
      ).toBeVisible();
    });

    await test.step("save and analyze a fictional job", async () => {
      await page.goto("/job-match");
      await expect(
        page.getByRole("heading", { name: "Application readiness" }),
      ).toBeVisible();
      await fillWhenReady(page.getByLabel("Job title"), jobTitle);
      await fillWhenReady(page.getByLabel("Company"), company);
      await fillWhenReady(page.getByLabel("Location"), "Remote");
      await selectWhenReady(page.getByLabel("Work model"), "remote");
      await selectWhenReady(page.getByLabel("Employment type"), "full_time");
      await fillWhenReady(
        page.getByLabel("Job description"),
        [
          `Title: ${jobTitle}`,
          `Company: ${company}`,
          "Location: Remote",
          "Requirements:",
          "- Must have conducted customer discovery interviews and synthesized research findings.",
          "- Collaborate with engineering and design on product experiments.",
          "- Preferred experience with product analytics.",
        ].join("\n"),
      );
      await clickWhenReady(page.getByRole("button", { name: "Save job" }));
      await expect(page.getByRole("status")).toContainText(
        `${jobTitle} saved for matching.`,
      );

      await clickWhenReady(page.getByRole("button", { name: "Analyze match" }));
      await expect(
        page.getByRole("table", {
          name: "Requirement-by-requirement job match evidence matrix",
        }),
      ).toBeVisible();
      await expect(page.getByText(evidenceTitle)).toBeVisible();
      await expect(
        page
          .getByText(/Rezumi scores are internal readiness measurements/i)
          .first(),
      ).toBeVisible();
    });

    await test.step("create a grounded immutable resume version", async () => {
      await page.goto("/resume-builder");
      await expect(
        page.getByRole("heading", { name: "Verified resume exports" }),
      ).toBeVisible();
      await fillWhenReady(page.getByLabel("Resume title"), resumeTitle);
      await fillWhenReady(page.getByLabel("Target role"), jobTitle);
      await selectWhenReady(
        page.getByLabel("Template"),
        "standard_professional",
      );
      await clickWhenReady(page.getByRole("button", { name: "Create" }));
      await expect(
        page
          .getByRole("status")
          .getByText("Resume created from eligible Career Record evidence."),
      ).toBeVisible();
      await expect(
        page.getByRole("listitem").filter({ hasText: evidenceStatement }),
      ).toBeVisible();
      await expect(page.getByText("Version 1").first()).toBeVisible();
    });

    await test.step("create an application pinned to the saved sources", async () => {
      await page.goto("/applications");
      await expect(
        page.getByRole("heading", {
          name: "Keep every application traceable",
        }),
      ).toBeVisible();
      await expect(
        page.getByText(/Rezumi never submits an application on your behalf/i),
      ).toBeVisible();

      const createPanel = page.locator("details").filter({
        has: page.getByText("Add an application", { exact: true }),
      });
      await expect(createPanel).toHaveCount(1);
      await clickWhenReady(
        createPanel.getByText("Add an application", { exact: true }),
      );
      await expect(createPanel).toHaveAttribute("open", "", {
        timeout: actionTimeout,
      });
      const savedJobSelect = createPanel.getByRole("combobox", {
        name: "Saved job",
        exact: true,
      });
      await expect(savedJobSelect).toBeVisible();
      const resumeSelect = createPanel.getByRole("combobox", {
        name: "Resume",
        exact: true,
      });
      await expect(resumeSelect).toBeVisible();
      await selectWhenReady(savedJobSelect, { index: 0 });
      await selectWhenReady(resumeSelect, { index: 0 });
      await expect(
        createPanel.getByLabel("Immutable resume version"),
      ).toBeEnabled();
      await selectWhenReady(
        createPanel.getByLabel("Immutable resume version"),
        { index: 0 },
      );
      await selectWhenReady(createPanel.getByLabel("Initial stage"), "saved");
      await fillWhenReady(
        createPanel.getByLabel("Application deadline"),
        applicationDeadline,
      );
      await fillWhenReady(
        createPanel.getByLabel("Follow-up date"),
        followUpDate,
      );
      await fillWhenReady(
        createPanel.getByLabel("Application source"),
        "Fictional referral",
      );
      await fillWhenReady(
        createPanel.getByLabel("Industry"),
        "Fictional software",
      );
      await clickWhenReady(
        createPanel.getByRole("button", { name: "Add application" }),
      );
      await expect(page.getByRole("status").first()).toContainText(
        `${jobTitle} added to your workspace.`,
      );
      await expect(createPanel).not.toHaveAttribute("open", "", {
        timeout: actionTimeout,
      });
      await expect(createPanel.getByLabel("Industry")).toBeHidden({
        timeout: actionTimeout,
      });
    });

    await test.step("use board, table, calendar, and the non-drag stage control", async () => {
      const board = page.getByRole("region", {
        name: "Applications Kanban board",
      });
      await expect(board).toBeVisible();
      const applicationCard = board
        .getByRole("article")
        .filter({ hasText: jobTitle });
      await expect(applicationCard).toBeVisible();
      await selectWhenReady(
        applicationCard.getByLabel(`Move ${jobTitle} to stage`),
        "preparing",
      );
      await clickWhenReady(
        applicationCard.getByRole("button", { name: "Move" }),
      );
      await expect(page.getByRole("status").first()).toContainText(
        `${jobTitle} moved to Preparing.`,
      );

      const tableView = page.getByRole("button", { name: "Table" });
      if (testInfo.project.name.includes("mobile")) {
        await focusWhenReady(tableView);
        await page.keyboard.press("Enter");
      } else {
        await clickWhenReady(tableView);
      }
      await expect(page).toHaveURL(/[?&]view=table/);
      const table = page.getByRole("table", {
        name: /Applications with stage, pinned resume version/i,
      });
      await expect(table).toBeVisible();
      await expect(
        table.getByRole("row", { name: new RegExp(jobTitle, "i") }),
      ).toContainText("Version 1");

      const calendarView = page.getByRole("button", { name: "Calendar" });
      if (testInfo.project.name.includes("mobile")) {
        await focusWhenReady(calendarView);
        await page.keyboard.press("Enter");
      } else {
        await clickWhenReady(calendarView);
      }
      await expect(page).toHaveURL(/[?&]view=calendar/);
      const calendar = page.getByRole("region", {
        name: "Application calendar agenda",
      });
      await expect(calendar).toBeVisible();
      await expect(
        calendar.getByRole("link", { name: jobTitle }).first(),
      ).toBeVisible();
      await clickWhenReady(
        calendar.getByRole("link", { name: jobTitle }).first(),
      );
    });

    await test.step("record workflow activity and inspect pinned provenance", async () => {
      await expect(
        page.getByRole("heading", { name: jobTitle, exact: true }),
      ).toBeVisible();
      await expect(
        page.getByRole("heading", { name: "Pinned sources" }),
      ).toBeVisible();
      await expect(page.getByText("Immutable version 1")).toBeVisible();
      await expect(page.getByText("1 exact revisions")).toBeVisible();
      await expect(
        page.getByRole("heading", { name: "Grounding snapshot" }),
      ).toBeVisible();
      await expect(page.getByText(evidenceStatement)).toBeVisible();

      await clickWhenReady(
        page.getByRole("tab", { name: /Tasks, notes & timeline/ }),
      );
      const tasks = page.getByRole("region", { name: "Tasks" });
      await fillWhenReady(
        tasks.getByLabel("Task", { exact: true }),
        "Prepare interview",
      );
      await fillWhenReady(tasks.getByLabel("Due date"), taskDueDate);
      await clickWhenReady(tasks.getByRole("button", { name: "Add" }));
      await expect(page.getByRole("status").first()).toContainText(
        "Task added.",
      );
      await expect(tasks.getByLabel("Task title")).toHaveValue(
        "Prepare interview",
      );

      const notes = page.getByRole("region", { name: "Notes" });
      await fillWhenReady(
        notes.getByLabel("Add a private application note"),
        "Fictional note: review the pinned discovery evidence.",
      );
      await clickWhenReady(notes.getByRole("button", { name: "Add note" }));
      await expect(page.getByRole("status").first()).toContainText(
        "Note added.",
      );
      await expect(
        notes.getByText(
          "Fictional note: review the pinned discovery evidence.",
        ),
      ).toBeVisible();

      const eventForm = page.getByRole("region", {
        name: "Record an event",
      });
      await selectWhenReady(eventForm.getByLabel("Event type"), "contact");
      await fillWhenReady(
        eventForm.getByLabel("Title"),
        "Fictional recruiter conversation",
      );
      await fillWhenReady(
        eventForm.getByLabel("Description"),
        "Recorded by the user for this fictional application.",
      );
      await clickWhenReady(
        eventForm.getByRole("button", { name: "Record event" }),
      );
      await expect(page.getByRole("status").first()).toContainText(
        "Timeline event recorded.",
      );
      await expect(
        page.getByText("Fictional recruiter conversation"),
      ).toBeVisible();
    });

    await test.step("generate a grounded pack and verify consistency", async () => {
      await clickWhenReady(
        page.getByRole("tab", { name: /Application packs/ }),
      );
      await expect(
        page.getByText(/Rezumi does not submit or send them/i),
      ).toBeVisible();
      await expect(page.getByLabel("Tailored Resume")).toBeChecked();
      await uncheckWhenReady(page.getByLabel("Cover Letter"));
      await clickWhenReady(
        page.getByRole("button", { name: "Generate grounded drafts" }),
      );
      await expect(page.getByRole("status").first()).toContainText(
        "Application pack generated from the pinned job, resume, claims, and evidence.",
      );
      await expect(page.getByText("Consistency: Passed")).toBeVisible();
      await expect(
        page
          .getByRole("status")
          .filter({ hasText: "Consistency check passed" }),
      ).toContainText(
        "No conflicting or unsupported application claims were reported",
      );

      await clickWhenReady(page.getByText("View generated documents"));
      await clickWhenReady(page.getByText("Tailored resume", { exact: true }));
      const provenance = page
        .getByRole("heading", { name: "Claim provenance" })
        .locator("..");
      await expect(provenance).toBeVisible();
      await expect(provenance.getByText(evidenceStatement)).toBeVisible();
      const supportCounts = provenance.getByText(
        /1 evidence link.*1 supported requirement/,
      );
      await expect(provenance.getByRole("listitem")).toHaveCount(1);
      await expect(supportCounts).toHaveCount(1);
      await expect(supportCounts).toBeVisible();
      await clickWhenReady(
        page.getByRole("button", { name: "Refresh checks" }),
      );
      await expect(page.getByRole("status").first()).toContainText(
        "Pack and consistency findings refreshed.",
      );

      await expect(
        page.getByRole("button", { name: /submit|send/i }),
      ).toHaveCount(0);
    });
  } finally {
    await request
      .delete(`${requireMailpitUrl()}/api/v1/search`, {
        params: { query: `to:${email}` },
      })
      .catch(() => undefined);
  }
});
