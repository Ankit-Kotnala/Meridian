import { randomUUID } from "node:crypto";

import { expect, test, type APIRequestContext } from "@playwright/test";

type MailpitSearchResponse = { messages?: Array<{ ID?: string }> };

const mailpitUrl = process.env.PLAYWRIGHT_MAILPIT_URL;
const password = `${randomUUID()}-aA1!`;

function requireMailpitUrl(): string {
  if (!mailpitUrl) {
    throw new Error(
      "PLAYWRIGHT_MAILPIT_URL is required for the full-stack career-record journey.",
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
      { message: "verification email to arrive", timeout: 15_000 },
    )
    .toBe(true);
  return link!;
}

test("a user maintains a career record and converts an explicit achievement to evidence", async ({
  page,
  request,
}, testInfo) => {
  test.skip(
    testInfo.project.name.includes("mobile"),
    "The primary career-record workflow is covered once on desktop; shared workspace navigation has separate mobile coverage.",
  );
  test.setTimeout(180_000);
  const email = `career-${randomUUID()}@e2e.invalid.example.com`;

  try {
    await page.goto("/register");
    await page.getByLabel("Name").fill("Career Record E2E");
    await page.getByLabel("Email address").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(
      page.getByRole("heading", { name: "Check your email" }),
    ).toBeVisible();

    const link = new URL(await verificationLink(request, email));
    await page.goto(`${link.pathname}${link.hash}`);
    await expect(
      page.getByRole("heading", { name: "Email verified" }),
    ).toBeVisible();
    await page.getByRole("link", { name: "Continue to sign in" }).click();
    await page.getByLabel("Email address").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page).toHaveURL(/\/(dashboard|onboarding)$/);

    await page.goto("/career-profile");
    await expect(
      page.getByRole("heading", { name: "Career profile" }),
    ).toBeVisible();
    await expect(page.getByText(/No employment recorded yet/)).toBeVisible();

    await page.getByRole("button", { name: "Add skill" }).click();
    await page.getByLabel("Skill name").fill("User research");
    await page.getByLabel("Proficiency (optional)").selectOption("advanced");
    await page.getByRole("button", { name: "Save skill" }).click();
    await expect(page.getByText("Skill saved.")).toBeVisible();

    await page.getByRole("button", { name: "Add career record" }).click();
    await page.getByLabel("Record type").selectOption("project");
    await page.getByLabel("Title").fill("Fictional onboarding study");
    await page
      .getByLabel("Description (optional)")
      .fill("A user-provided record of a fictional study.");
    await page.getByRole("button", { name: "Save record" }).click();
    await expect(page.getByText("Career record saved.")).toBeVisible();

    await page.getByRole("button", { name: "Add employment" }).click();
    await page.getByLabel("Employer").fill("Fictional Products Ltd");
    await page.getByLabel("Official title").fill("Product Researcher");
    await page.getByLabel("Start month").fill("2024-04");
    await page
      .getByRole("checkbox", { name: "User research", exact: true })
      .check();
    await page.getByRole("button", { name: "Add experience" }).click();
    await expect(
      page.getByText("Employment added to your career profile."),
    ).toBeVisible();

    await page.goto("/evidence");
    await expect(
      page.getByRole("heading", { name: "Evidence Vault", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Add evidence" }).click();
    await page
      .getByLabel("Evidence title")
      .fill("Onboarding study source note");
    await page.getByLabel("Evidence type").selectOption("user_note");
    await page
      .getByLabel("Description")
      .fill("User states that they completed a fictional onboarding study.");
    await page
      .getByLabel("Product Researcher at Fictional Products Ltd")
      .check();
    await page
      .getByRole("checkbox", { name: "User research", exact: true })
      .check();
    await page.getByRole("button", { name: "Save evidence" }).click();
    await expect(
      page.getByText("Evidence saved.", { exact: false }),
    ).toBeVisible();

    const evidenceRow = page.getByRole("row", {
      name: /Onboarding study source note/,
    });
    await evidenceRow.getByRole("link", { name: "Review" }).click();
    await expect(
      page.getByRole("heading", {
        name: "Onboarding study source note",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByText("Not eligible for factual generation"),
    ).toBeVisible();
    await page.getByRole("button", { name: "Confirm evidence" }).click();
    await expect(
      page.getByText("Evidence confirmed.", { exact: false }),
    ).toBeVisible();

    await page.goto("/achievement-inbox");
    await expect(
      page.getByRole("heading", { name: "Achievement Inbox", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Capture achievement" })
      .first()
      .click();
    await page.getByLabel("Draft title").fill("Fictional release outcome");
    await page
      .getByLabel("What did you deliver?")
      .fill("A fictional onboarding release");
    await page
      .getByLabel("What problem did it address?")
      .fill("A user-reported onboarding problem");
    await page
      .getByLabel("What changed as a result?")
      .fill("The user reports that the flow became clearer");
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(
      page.getByText("Achievement draft saved.", { exact: false }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Convert to evidence" }).click();
    const dialog = page.getByRole("dialog", {
      name: "Convert this achievement?",
    });
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Convert to evidence" }).click();
    await expect(
      page.getByText("Achievement converted to evidence.", { exact: false }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Review evidence" }),
    ).toBeVisible();
  } finally {
    await request
      .delete(`${requireMailpitUrl()}/api/v1/search`, {
        params: { query: `to:${email}` },
      })
      .catch(() => undefined);
  }
});
