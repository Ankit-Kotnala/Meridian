import { randomUUID } from "node:crypto";
import path from "node:path";

import {
  expect,
  test,
  type APIRequestContext,
  type BrowserContext,
  type Page,
} from "@playwright/test";

import { SCORE_DISCLAIMER_PATTERN } from "./helpers/job-match-fixtures";

type MailpitSearchResponse = {
  messages?: Array<{ ID?: string }>;
};

const mailpitUrl = process.env.PLAYWRIGHT_MAILPIT_URL;
const password = `${randomUUID()}-aA1!`;
const secondaryDeviceLabel = "Browser on device";
const resumeFixture = path.resolve(
  process.cwd(),
  "../test-fixtures/generated/fictional-resume.pdf",
);

function requireMailpitUrl(): string {
  if (!mailpitUrl) {
    throw new Error(
      "PLAYWRIGHT_MAILPIT_URL is required for the full-stack auth journey.",
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

async function waitForVerificationLink(
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

async function removeMail(
  request: APIRequestContext,
  email: string,
): Promise<void> {
  await request.delete(`${requireMailpitUrl()}/api/v1/search`, {
    params: { query: `to:${email}` },
  });
}

async function signIn(page: Page, email: string): Promise<void> {
  await page.goto("/login");
  await expect(
    page.getByRole("heading", { name: "Sign in to Meridian" }),
  ).toBeVisible();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/(dashboard|onboarding)$/);
}

async function finishOnboarding(page: Page): Promise<void> {
  await page.goto("/onboarding");
  await expect(
    page.getByRole("heading", { name: "Set up your Meridian workspace" }),
  ).toBeVisible();

  const saveProfile = page.getByRole("button", { name: "Save and continue" });
  await saveProfile.focus();
  await saveProfile.press("Enter");
  await page.getByRole("button", { name: "Continue without a resume" }).click();
  await page.getByRole("button", { name: "Continue to preferences" }).click();
  await page.getByRole("button", { name: "Finish onboarding" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", {
      name: "Start with your resume or build your profile by hand.",
    }),
  ).toBeVisible();
}

async function completeResumeHealth(page: Page): Promise<void> {
  await page.goto("/resume-health/account");
  await expect(
    page.getByRole("heading", { name: "Resumes", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Resume file").setInputFiles(resumeFixture);
  await page.getByRole("button", { name: "Upload and review" }).click();
  await expect(page).toHaveURL(
    /\/resume-health\/account\/(?:processing|review)\//,
  );
  await expect(page).toHaveURL(/\/resume-health\/account\/review\//, {
    timeout: 120_000,
  });
  await expect(
    page.getByRole("heading", { name: "Review what Meridian extracted" }),
  ).toBeVisible();
  const reviewedField = page.getByLabel(/^Reviewed /).first();
  const correctedValue = `${await reviewedField.inputValue()} [E2E reviewed fixture]`;
  await reviewedField.fill(correctedValue);
  await expect(reviewedField).toHaveValue(correctedValue);
  const correctionResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      /\/api\/v1\/documents\/[^/]+\/canonical-resume(?:\?|$)/.test(
        response.url(),
      ) &&
      response.ok(),
  );
  const analyze = page.getByRole("button", { name: "Save review and analyze" });
  await analyze.focus();
  await analyze.press("Enter");
  const correctedCanonical = (await (
    await correctionResponse
  ).json()) as unknown;
  expect(JSON.stringify(correctedCanonical)).toContain(correctedValue);
  expect(correctedCanonical).toEqual(
    expect.objectContaining({ correctedByUser: true }),
  );
  await expect(page).toHaveURL(
    /\/resume-health\/account\/(?:processing|report)\//,
  );
  await expect(page).toHaveURL(/\/resume-health\/account\/report\//, {
    timeout: 120_000,
  });
  await expect(
    page.getByRole("heading", { name: "Resume Health" }),
  ).toBeVisible();
  await expect(
    page
      .getByText(SCORE_DISCLAIMER_PATTERN)
      .first(),
  ).toBeVisible();
  await expect(
    page
      .getByRole("img", { name: /Resume Health Score:/ })
      .or(page.getByText("Score unavailable")),
  ).toBeVisible();

  await page.goto("/onboarding");
  await expect(page.getByText("Status: Analysis ready")).toHaveCount(2);
  await page.goto("/dashboard");

  await page.goto("/dashboard");
  await expect(
    page
      .getByRole("img", { name: /Resume Health Score:/ })
      .or(page.getByText("Score unavailable")),
  ).toBeVisible();
}

test("a verified user completes honest onboarding and controls sessions", async ({
  browser,
  page,
  request,
}, testInfo) => {
  test.setTimeout(240_000);
  const suffix = `${testInfo.project.name.replace(/[^a-z0-9]/gi, "-")}-${randomUUID()}`;
  const email = `e2e-${suffix}@e2e.invalid.example.com`;
  const displayName = `E2E ${testInfo.project.name}`;
  let secondaryContext: BrowserContext | undefined;

  try {
    await page.goto("/register");
    await expect(
      page.getByRole("heading", { name: "Start your Meridian account" }),
    ).toBeVisible();

    await page.keyboard.press("Tab");
    await expect(
      page.getByRole("link", { name: "Skip to main content" }),
    ).toBeFocused();

    await page.getByLabel("Name").fill(displayName);
    await page.getByLabel("Email address").fill(email);
    const registrationPassword = page.getByLabel("Password", { exact: true });
    await registrationPassword.fill(password);
    await registrationPassword.press("Enter");
    await expect(
      page.getByRole("heading", { name: "Check your email" }),
    ).toBeVisible();

    const verificationLink = new URL(
      await waitForVerificationLink(request, email),
    );
    const expectedOrigin = new URL(String(testInfo.project.use.baseURL)).origin;
    expect(verificationLink.origin).toBe(expectedOrigin);
    expect(verificationLink.pathname).toBe("/verify-email");
    expect(verificationLink.search).toBe("");
    try {
      await page.goto(`${verificationLink.pathname}${verificationLink.hash}`);
    } catch {
      throw new Error(
        "The verification page could not be reached before its one-time token was consumed.",
      );
    }
    await expect(
      page.getByRole("heading", { name: "Email verified" }),
    ).toBeVisible();
    await page.getByRole("link", { name: "Continue to sign in" }).click();

    await page.getByLabel("Email address").fill(email);
    const loginPassword = page.getByLabel("Password", { exact: true });
    await loginPassword.fill(password);
    await loginPassword.press("Enter");
    await expect(page).toHaveURL(/\/(dashboard|onboarding)$/);

    await finishOnboarding(page);
    await completeResumeHealth(page);

    if (testInfo.project.name.includes("mobile")) {
      const openNavigation = page.getByRole("button", {
        name: "Open application navigation",
      });
      await openNavigation.focus();
      await openNavigation.press("Enter");
      await expect(
        page.getByRole("dialog", { name: "Application navigation" }),
      ).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(openNavigation).toBeFocused();
    }

    const baseURL = String(testInfo.project.use.baseURL);
    secondaryContext = await browser.newContext({
      baseURL,
      userAgent: "Rezumi-E2E-Secondary/1.0",
    });
    const secondaryPage = await secondaryContext.newPage();
    await signIn(secondaryPage, email);
    await expect(secondaryPage).toHaveURL(/\/dashboard$/);

    await page.goto("/settings/sessions");
    const revokeSession = page.getByRole("button", {
      name: `Revoke ${secondaryDeviceLabel}`,
    });
    await expect(revokeSession).toHaveCount(1);
    await revokeSession.click();
    await expect(revokeSession).toHaveCount(0);

    await expect
      .poll(
        async () =>
          (await secondaryContext!.request.get("/api/v1/me")).status(),
        { message: "the revoked session to lose API access", timeout: 10_000 },
      )
      .toBe(401);

    await secondaryPage.goto("/dashboard");
    await expect(secondaryPage).toHaveURL(/\/login(?:\?|$)/, {
      timeout: 15_000,
    });
    await secondaryContext.close();
    secondaryContext = undefined;

    await page.goto("/settings/security");
    await expect(
      page.getByRole("heading", { name: "Change password" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Security activity" }),
    ).toBeVisible();
    await page.goto("/settings/notifications");
    await expect(
      page.getByText("Scheduled delivery is not configured"),
    ).toBeVisible();
    await page.goto("/settings/privacy");
    await expect(page.getByText("Export is unavailable")).toBeVisible();

    await page.getByRole("button", { name: /Account menu for/i }).click();
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await expect(page).toHaveURL(/\/login$/);
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login(?:\?|$)/);
  } finally {
    await secondaryContext?.close();
    await removeMail(request, email).catch(() => undefined);
  }
});
