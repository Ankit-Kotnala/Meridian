import { randomUUID } from "node:crypto";

import { expect, test, type APIRequestContext } from "@playwright/test";

type MailpitSearchResponse = { messages?: Array<{ ID?: string }> };

const mailpitUrl = process.env.PLAYWRIGHT_MAILPIT_URL;
const password = `${randomUUID()}-aA1!`;

function requireMailpitUrl(): string {
  if (!mailpitUrl) {
    throw new Error(
      "PLAYWRIGHT_MAILPIT_URL is required for the full-stack resume-builder journey.",
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

test("a user builds a grounded resume and verifies a PDF export", async ({
  page,
  request,
}, testInfo) => {
  test.skip(
    testInfo.project.name.includes("mobile"),
    "The resume-builder primary workflow is covered once on desktop; shared navigation has separate mobile coverage.",
  );
  test.setTimeout(180_000);
  const email = `resume-builder-${randomUUID()}@e2e.invalid.example.com`;

  try {
    await page.goto("/register");
    await page.getByLabel("Name").fill("Resume Builder E2E");
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
    await page.getByRole("button", { name: "Add contact fact" }).click();
    await page
      .getByRole("textbox", { name: "Value", exact: true })
      .fill("Resume Builder E2E");
    await page
      .getByLabel("Use as the primary value for this fact type")
      .check();
    await page.getByRole("button", { name: "Save contact fact" }).click();
    await expect(
      page.getByText(
        "Contact fact saved. Confirm it separately before downstream use.",
      ),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "More actions for the Name contact fact" })
      .click();
    await page.getByRole("menuitem", { name: "Confirm current value" }).click();
    await expect(page.getByText("Contact fact confirmed.")).toBeVisible();

    await page.getByRole("button", { name: "Add skill" }).click();
    await page.getByLabel("Skill name").fill("Product discovery");
    await page.getByLabel("Proficiency (optional)").selectOption("advanced");
    await page.getByRole("button", { name: "Save skill" }).click();
    await expect(page.getByText("Skill saved.")).toBeVisible();

    await page.getByRole("button", { name: "Add employment" }).click();
    await page.getByLabel("Employer").fill("Fictional Products Ltd");
    await page.getByLabel("Official title").fill("Product Researcher");
    await page.getByLabel("Start month").fill("2024-04");
    await page
      .getByRole("checkbox", { name: "Product discovery", exact: true })
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
    await page.getByLabel("Evidence title").fill("Discovery resume source");
    await page.getByLabel("Evidence type").selectOption("user_note");
    await page
      .getByLabel("Description")
      .fill("User states they completed customer discovery interviews.");
    await page
      .getByLabel("Product Researcher at Fictional Products Ltd")
      .check();
    await page
      .getByRole("checkbox", { name: "Product discovery", exact: true })
      .check();
    await page.getByRole("button", { name: "Save evidence" }).click();
    await expect(
      page.getByText("Evidence saved.", { exact: false }),
    ).toBeVisible();

    await page
      .getByRole("row", { name: /Discovery resume source/ })
      .getByRole("link", { name: "Review" })
      .click();
    await expect(
      page.getByRole("heading", {
        name: "Discovery resume source",
        exact: true,
      }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Confirm evidence" }).click();
    await expect(
      page.getByText("Evidence confirmed.", { exact: false }),
    ).toBeVisible();

    await page.goto("/resume-builder");
    await expect(
      page.getByRole("heading", { name: "Resume Builder" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "No resumes yet" }),
    ).toBeVisible();
    await page.getByLabel("Resume title").fill("Discovery Resume");
    await page.getByLabel("Target role").fill("Senior Product Manager");
    await page.getByLabel("Template").selectOption("standard_professional");
    await page.getByRole("button", { name: "Create" }).click();
    await expect(
      page
        .getByRole("status")
        .getByText("Resume created from eligible Career Record evidence."),
    ).toBeVisible();
    await expect(
      page.getByRole("listitem").filter({
        hasText: "User states they completed customer discovery interviews.",
      }),
    ).toBeVisible();

    await page.getByLabel("Export format").selectOption("pdf");
    await page.getByRole("button", { name: "Verify" }).click();
    await expect(page.getByText("Round-trip verified")).toBeVisible();
    await page.getByRole("button", { name: "Download" }).click();
    await expect(page.getByText(/https?:\/\/.+resume\.pdf/)).toBeVisible();
  } finally {
    await request
      .delete(`${requireMailpitUrl()}/api/v1/search`, {
        params: { query: `to:${email}` },
      })
      .catch(() => undefined);
  }
});
