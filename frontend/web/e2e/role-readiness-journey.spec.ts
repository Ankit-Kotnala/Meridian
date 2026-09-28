import { randomUUID } from "node:crypto";

import { expect, test, type APIRequestContext } from "@playwright/test";

import { SCORE_DISCLAIMER_PATTERN } from "./helpers/job-match-fixtures";

type MailpitSearchResponse = { messages?: Array<{ ID?: string }> };

const mailpitUrl = process.env.PLAYWRIGHT_MAILPIT_URL;
const password = `${randomUUID()}-aA1!`;

function requireMailpitUrl(): string {
  if (!mailpitUrl) {
    throw new Error(
      "PLAYWRIGHT_MAILPIT_URL is required for the full-stack role-readiness journey.",
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

test("a user saves, analyzes, and compares evidence-linked target roles", async ({
  page,
  request,
}, testInfo) => {
  test.skip(
    testInfo.project.name.includes("mobile"),
    "The Role Explorer primary workflow is covered once on desktop; shared navigation has separate mobile coverage.",
  );
  test.setTimeout(180_000);
  const email = `role-${randomUUID()}@e2e.invalid.example.com`;

  try {
    await page.goto("/register");
    await page.getByLabel("Name").fill("Role Readiness E2E");
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
    await page
      .getByLabel("Evidence title")
      .fill("Onboarding study source note");
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
      .getByRole("row", { name: /Onboarding study source note/ })
      .getByRole("link", { name: "Review" })
      .click();
    await expect(
      page.getByRole("heading", {
        name: "Onboarding study source note",
        exact: true,
      }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Confirm evidence" }).click();
    await expect(
      page.getByText("Evidence confirmed.", { exact: false }),
    ).toBeVisible();

    await page.goto("/role-explorer");
    await expect(
      page.getByRole("heading", { name: "Role readiness" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Matching roles" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "No saved roles" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "No readiness analysis" }),
    ).toBeVisible();

    await page.getByLabel("Search roles").fill("product manager");
    await page.getByRole("button", { name: "Search" }).click();
    const productRole = page.locator("article").filter({
      has: page.getByRole("heading", { name: "Product Manager" }),
      hasText: "Owns product discovery",
    });
    await expect(productRole).toBeVisible();
    await productRole.getByRole("button", { name: "Save" }).click();
    await expect(page.getByRole("status")).toContainText(
      "Product Manager saved.",
    );

    const savedRole = page.locator("article").filter({
      has: page.getByRole("heading", { name: "Product Manager" }),
      hasText: "Version",
    });
    await savedRole
      .getByRole("textbox", { name: "Notes" })
      .fill("Primary role target for customer discovery evidence.");
    await savedRole.getByRole("button", { name: "Save notes" }).click();
    await expect(page.getByRole("status")).toContainText(
      "Product Manager notes saved.",
    );
    await savedRole.getByRole("button", { name: "Analyze" }).click();
    await expect(page.getByRole("status")).toContainText(
      "Product Manager readiness analyzed.",
    );

    await expect(
      page.getByText(/Product Manager readiness is based on/),
    ).toBeVisible();
    await expect(
      page.getByText(SCORE_DISCLAIMER_PATTERN).first(),
    ).toBeVisible();
    await expect(page.getByText("Onboarding study source note")).toBeVisible();
    await expect(page.getByText("Confirmed evidence")).toBeVisible();
    await expect(
      page.getByRole("table", { name: /Requirement to evidence/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Readiness history" }),
    ).toBeVisible();

    await productRole.getByRole("button", { name: "Compare" }).click();
    await page.getByLabel("Search roles").fill("software engineer");
    await page.getByRole("button", { name: "Search" }).click();
    const engineerRole = page.locator("article").filter({
      has: page.getByRole("heading", { name: "Software Engineer" }),
    });
    await expect(engineerRole).toBeVisible();
    await engineerRole.getByRole("button", { name: "Compare" }).click();
    await page.getByRole("button", { name: "Compare selected" }).click();
    await expect(
      page.getByRole("heading", { name: "Role comparison" }),
    ).toBeVisible();
    const comparisonSection = page.locator("section").filter({
      has: page.getByRole("heading", { name: "Role comparison" }),
    });
    await expect(
      comparisonSection.getByText("Required gaps", { exact: true }).first(),
    ).toBeVisible();
  } finally {
    await request
      .delete(`${requireMailpitUrl()}/api/v1/search`, {
        params: { query: `to:${email}` },
      })
      .catch(() => undefined);
  }
});
