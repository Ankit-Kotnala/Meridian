import { randomUUID } from "node:crypto";

import { expect, test, type APIRequestContext } from "@playwright/test";

type MailpitSearchResponse = { messages?: Array<{ ID?: string }> };

const mailpitUrl = process.env.PLAYWRIGHT_MAILPIT_URL;
const password = `${randomUUID()}-aA1!`;

function requireMailpitUrl(): string {
  if (!mailpitUrl) {
    throw new Error(
      "PLAYWRIGHT_MAILPIT_URL is required for the full-stack job-match journey.",
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

test("a user saves a job, analyzes exact requirements, and prioritizes it", async ({
  page,
  request,
}, testInfo) => {
  test.skip(
    testInfo.project.name.includes("mobile"),
    "The Job Match primary workflow is covered once on desktop; shared navigation has separate mobile coverage.",
  );
  test.setTimeout(180_000);
  const email = `job-${randomUUID()}@e2e.invalid.example.com`;

  try {
    await page.goto("/register");
    await page.getByLabel("Name").fill("Job Match E2E");
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
    await page.getByRole("button", { name: "Add skill" }).click();
    await page.getByLabel("Skill name").fill("User research");
    await page.getByLabel("Proficiency (optional)").selectOption("advanced");
    await page.getByRole("button", { name: "Save skill" }).click();
    await expect(page.getByText("Skill saved.")).toBeVisible();

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
    await page.getByLabel("Evidence title").fill("Discovery interview notes");
    await page.getByLabel("Evidence type").selectOption("user_note");
    await page
      .getByLabel("Description")
      .fill("User states that they completed customer discovery interviews.");
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

    await page
      .getByRole("row", { name: /Discovery interview notes/ })
      .getByRole("link", { name: "Review" })
      .click();
    await expect(
      page.getByRole("heading", {
        name: "Discovery interview notes",
        exact: true,
      }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Confirm evidence" }).click();
    await expect(
      page.getByText("Evidence confirmed.", { exact: false }),
    ).toBeVisible();

    await page.goto("/job-match");
    await expect(
      page.getByRole("heading", { name: "Application readiness" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "No saved jobs" }),
    ).toBeVisible();

    await page.getByLabel("Job title").fill("Product Manager");
    await page.getByLabel("Company").fill("Example Co");
    await page.getByLabel("Location").fill("Remote");
    await page.getByLabel("Work model").selectOption("remote");
    await page.getByLabel("Employment type").selectOption("full_time");
    await page
      .getByLabel("Job description")
      .fill(
        [
          "Title: Product Manager",
          "Company: Example Co",
          "Location: Remote",
          "Requirements:",
          "- Must have experience with user research and customer discovery.",
          "- Build product experiments with engineering and design.",
          "- Preferred experience with SaaS analytics.",
        ].join("\n"),
      );
    await page.getByRole("button", { name: "Save job" }).click();
    await expect(page.getByRole("status")).toContainText(
      "Product Manager saved for matching.",
    );

    await page.getByRole("button", { name: "Analyze match" }).click();
    await expect(
      page.getByRole("table", {
        name: "Requirement-by-requirement job match evidence matrix",
      }),
    ).toBeVisible();
    await expect(page.getByText("Discovery interview notes")).toBeVisible();
    await expect(
      page.getByText(/Rezumi scores are internal readiness measurements/i),
    ).toBeVisible();

    await page.getByLabel("Interest").fill("5");
    await page.getByLabel("Career direction fit").fill("4");
    await page.getByLabel("Location fit").selectOption("strong");
    await page.getByLabel("Work model fit").selectOption("strong");
    await page.getByRole("button", { name: "Calculate priority" }).click();
    await expect(
      page.getByText("Address mandatory gaps before tailoring."),
    ).toBeVisible();
  } finally {
    await request
      .delete(`${requireMailpitUrl()}/api/v1/search`, {
        params: { query: `to:${email}` },
      })
      .catch(() => undefined);
  }
});
