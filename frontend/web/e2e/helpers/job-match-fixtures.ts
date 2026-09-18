import { randomUUID } from "node:crypto";

import { expect, type Page } from "@playwright/test";

export type SavedJobFixture = {
  company: string;
  description: string;
  title: string;
};

function requestOrigin(page: Page): string {
  try {
    return new URL(page.url()).origin;
  } catch {
    const baseUrl = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000";
    return new URL(baseUrl).origin;
  }
}

async function csrfToken(page: Page): Promise<string> {
  const cookies = await page.context().cookies();
  const token = cookies.find((cookie) => cookie.name === "rezumi_csrf")?.value;
  if (!token) {
    throw new Error("Missing rezumi_csrf cookie for authenticated API writes.");
  }
  try {
    return decodeURIComponent(token);
  } catch {
    return token;
  }
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
      Origin: requestOrigin(page),
      "X-CSRF-Token": await csrfToken(page),
    },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
}

export async function analyzeFirstSavedJob(page: Page): Promise<void> {
  await page.goto("/job-match/saved");
  await expect(page.getByRole("heading", { name: "Saved jobs" })).toBeVisible();
  await page.getByRole("button", { name: "Analyze match" }).click();
  await expect(
    page.getByRole("table", {
      name: "Requirement-by-requirement job match evidence matrix",
    }),
  ).toBeVisible();
}
