import { randomUUID } from "node:crypto";

import { expect, type APIResponse, type Page } from "@playwright/test";

export type SavedJobFixture = {
  company: string;
  description: string;
  title: string;
};

/** API payloads use Rezumi; some account UI surfaces use Meridian. */
export const SCORE_DISCLAIMER_PATTERN =
  /(Rezumi|Meridian) scores are internal readiness measurements/i;

export const CANONICAL_SCORE_DISCLAIMER =
  "Rezumi scores are internal readiness measurements. They are not scores provided by an employer or applicant tracking system and do not guarantee interviews or employment outcomes.";

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

async function authenticatedJsonRequest(
  page: Page,
  method: "GET" | "POST",
  path: string,
  data?: unknown,
): Promise<APIResponse> {
  const headers: Record<string, string> = {
    Origin: requestOrigin(page),
    "X-CSRF-Token": await csrfToken(page),
  };
  if (data !== undefined) {
    headers["Content-Type"] = "application/json";
    headers["Idempotency-Key"] = randomUUID();
  }
  return page.request.fetch(path, { method, headers, data });
}

export async function fetchFirstApplicationId(page: Page): Promise<string> {
  const response = await authenticatedJsonRequest(page, "GET", "/api/v1/applications");
  expect(response.ok(), await response.text()).toBeTruthy();
  const body = (await response.json()) as { data?: Array<{ id?: string }> };
  const applicationId = body.data?.[0]?.id;
  if (!applicationId) {
    throw new Error(
      "Expected at least one application from the grounded application chain.",
    );
  }
  return applicationId;
}

export async function createInterviewSessionThroughApi(
  page: Page,
  input: {
    applicationId: string;
    kind: "behavioral" | "recruiter_screen" | "technical" | "hiring_manager" | "panel" | "other";
    title: string;
  },
): Promise<string> {
  const response = await authenticatedJsonRequest(
    page,
    "POST",
    "/api/v1/interview-prep/sessions",
    input,
  );
  expect(response.ok(), await response.text()).toBeTruthy();
  const body = (await response.json()) as { id?: string };
  if (!body.id) {
    throw new Error("Interview session create response did not include an id.");
  }
  return body.id;
}

/** Create a pasted job through the API (the manual entry form was removed from the UI). */
export async function createSavedJobThroughApi(
  page: Page,
  job: SavedJobFixture,
): Promise<void> {
  const response = await authenticatedJsonRequest(page, "POST", "/api/v1/jobs", {
    company: job.company,
    employmentType: "full_time",
    location: "Remote",
    sourceKind: "paste",
    sourceText: job.description,
    title: job.title,
    workModel: "remote",
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
