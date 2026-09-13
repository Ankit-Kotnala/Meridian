import { randomUUID } from "node:crypto";

import { expect, type Page } from "@playwright/test";

export type SavedJobFixture = {
  company: string;
  description: string;
  title: string;
};

async function csrfToken(page: Page): Promise<string> {
  const cookies = await page.context().cookies();
  const token = cookies.find((cookie) => cookie.name === "rezumi_csrf")?.value;
  if (!token) {
    throw new Error("Missing rezumi_csrf cookie for authenticated API writes.");
  }
  return token;
}

/** Create a pasted job through the API (the manual entry form was removed from the UI). */
export async function createSavedJobThroughApi(
  page: Page,
  job: SavedJobFixture,
): Promise<void> {
  const response = await page.request.post("/api/v1/jobs", {
    data: {
      company: job.company,
      employmentType: "full_time",
      location: "Remote",
      sourceKind: "paste",
      sourceText: job.description,
      title: job.title,
      workModel: "remote",
    },
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": randomUUID(),
      "X-CSRF-Token": await csrfToken(page),
    },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
}

export async function analyzeFirstSavedJob(page: Page): Promise<void> {
  await page.goto("/job-match/saved");
  await expect(
    page.getByRole("heading", { name: "Saved jobs" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Analyze match" }).click();
  await expect(
    page.getByRole("table", {
      name: "Requirement-by-requirement job match evidence matrix",
    }),
  ).toBeVisible();
}
