import path from "node:path";

import { expect, test } from "@playwright/test";

const resumeFixture = path.resolve(
  process.cwd(),
  "../../packages/test-fixtures/generated/fictional-resume.pdf",
);

test("a guest reviews a short-lived report without silent account transfer", async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name.includes("mobile"),
    "The registered journey covers the primary mobile upload and review workflow.",
  );
  test.setTimeout(180_000);

  await page.goto("/resume-health/guest");
  await expect(
    page.getByRole("heading", {
      name: "Check one resume before creating an account",
    }),
  ).toBeVisible();
  await page.getByLabel("Resume file").setInputFiles(resumeFixture);
  await page.getByRole("button", { name: "Upload and review" }).click();
  await expect(page).toHaveURL(/\/resume-health\/guest\/processing\//);
  await expect(page).toHaveURL(/\/resume-health\/guest\/review\//, {
    timeout: 120_000,
  });
  const canonicalCorrections: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "PATCH" &&
      /\/api\/v1\/guest\/documents\/[^/]+\/canonical-resume(?:\?|$)/.test(
        request.url(),
      )
    ) {
      canonicalCorrections.push(request.url());
    }
  });
  const analysisResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v1\/guest\/resume-health(?:\?|$)/.test(response.url()),
  );
  await page.getByRole("button", { name: "Save review and analyze" }).click();
  const accepted = await analysisResponse;
  expect(
    accepted.ok(),
    `guest analysis start returned HTTP ${accepted.status()}`,
  ).toBe(true);
  expect(canonicalCorrections).toEqual([]);
  await expect(page).toHaveURL(/\/resume-health\/guest\/report\//, {
    timeout: 120_000,
  });

  await expect(
    page.getByRole("heading", { name: "Guest retention and optional save" }),
  ).toBeVisible();
  await page
    .getByRole("checkbox", { name: "Save this guest resume to my account" })
    .check();
  await page.getByRole("button", { name: "Save to my account" }).click();
  await expect(
    page.getByRole("link", { name: "Sign in and return" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/resume-health\/guest\/report\//);

  await page.getByRole("button", { name: "Delete resume" }).click();
  const dialog = page.getByRole("dialog", {
    name: "Delete this resume and report?",
  });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Delete resume" }).click();
  await expect(page).toHaveURL(/\/resume-health\/guest\/processing\//);
  await expect(
    page.getByRole("heading", { name: "Resume deletion complete" }),
  ).toBeVisible({ timeout: 120_000 });
  await page.getByRole("link", { name: "Return to Resume Health" }).click();
  await expect(page).toHaveURL(/\/resume-health\/guest$/);
});
