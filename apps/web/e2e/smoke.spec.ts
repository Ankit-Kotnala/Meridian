import { expect, test } from "@playwright/test";

test("public landing page presents the core promise", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", {
      level: 1,
      name: /the system of record behind your career/i,
    }),
  ).toBeVisible();
  await expect(page.getByText("No unsupported claims")).toBeVisible();
  await expect(
    page.getByRole("link", { name: /explore the fictional demo/i }).first(),
  ).toBeVisible();
});

test("dashboard is explicit about fictional data and score limits", async ({
  page,
}) => {
  await page.goto("/demo/dashboard");

  await expect(
    page.getByText(/fictional demo data · product preview only/i),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: /good morning, jordan lee/i }),
  ).toBeVisible();
  await expect(
    page.getByText(
      /not scores provided by an employer or applicant tracking system/i,
    ),
  ).toBeVisible();
});

test("mobile navigation can be opened with a named control", async ({
  page,
}, testInfo) => {
  test.skip(
    !testInfo.project.name.includes("mobile"),
    "Mobile-only navigation check",
  );
  await page.goto("/");

  await page.getByRole("button", { name: "Open navigation menu" }).click();
  await expect(
    page.getByRole("navigation", { name: "Mobile navigation" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Explore demo" })).toBeVisible();
});

test("health endpoint is live", async ({ request }) => {
  const response = await request.get("/api/health");
  expect(response.ok()).toBeTruthy();
  await expect(response.json()).resolves.toMatchObject({
    service: "careeros-web",
    status: "ok",
  });
});
