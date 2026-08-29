import { randomUUID } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { chromium } from "@playwright/test";

const argumentsMap = Object.fromEntries(
  process.argv.slice(2).map((argument) => {
    const [key, ...value] = argument.replace(/^--/, "").split("=");
    return [key, value.join("=")];
  }),
);

const baseUrl = argumentsMap.baseUrl ?? "http://127.0.0.1:3000";
const authBaseUrl = argumentsMap.authBaseUrl ?? baseUrl;
const outputDirectory = path.resolve(
  process.cwd(),
  argumentsMap.output ?? "../../docs/screenshots/ux-redesign/after",
);

const routeCatalog = {
  home: "/",
  demo: "/demo/dashboard",
  product: "/product",
  login: "/login",
  register: "/register",
  forgotPassword: "/forgot-password",
  resetPassword: "/reset-password",
  verifyEmail: "/verify-email",
  getStarted: "/get-started",
  guestResumeHealth: "/resume-health/guest",
  dashboard: "/dashboard",
  onboarding: "/onboarding",
  careerProfile: "/career-profile",
  careerImports: "/career-profile/imports",
  evidence: "/evidence",
  achievementInbox: "/achievement-inbox",
  roleExplorer: "/role-explorer",
  jobMatch: "/job-match",
  applications: "/applications",
  accountResumeHealth: "/resume-health/account",
  resumeBuilder: "/resume-builder",
  changeStudio: "/change-studio",
  interviewPrep: "/interview-prep",
  networking: "/networking",
  careerGrowth: "/career-growth",
  analytics: "/analytics",
  settingsProfile: "/settings",
  settingsSecurity: "/settings/security",
  settingsSessions: "/settings/sessions",
  settingsNotifications: "/settings/notifications",
  settingsConnections: "/settings/connections",
  settingsConsent: "/settings/consent",
  settingsPrivacy: "/settings/privacy",
  settingsBilling: "/settings/billing",
};

const publicRouteNames = ["home", "demo", "login", "guestResumeHealth"];
const protectedRouteNames = [
  "dashboard",
  "onboarding",
  "careerProfile",
  "careerImports",
  "evidence",
  "achievementInbox",
  "roleExplorer",
  "jobMatch",
  "applications",
  "accountResumeHealth",
  "resumeBuilder",
  "changeStudio",
  "interviewPrep",
  "networking",
  "careerGrowth",
  "analytics",
  "settingsProfile",
  "settingsSecurity",
  "settingsSessions",
  "settingsNotifications",
  "settingsConnections",
  "settingsConsent",
  "settingsPrivacy",
  "settingsBilling",
];

const viewportCatalog = {
  320: { width: 320, height: 720 },
  360: { width: 360, height: 780 },
  393: { width: 393, height: 852 },
  768: { width: 768, height: 1024 },
  1024: { width: 1024, height: 900 },
  1440: { width: 1440, height: 1000 },
  1920: { width: 1920, height: 1080 },
};

function select(catalog, requested, label, fallbackKeys) {
  const keys = requested ? requested.split(",") : fallbackKeys;
  return keys.map((key) => {
    const value = catalog[key];
    if (!value) throw new Error(`Unknown ${label}: ${key}`);
    return [key, value];
  });
}

const authenticated = argumentsMap.authenticated === "true";
const routes = select(
  routeCatalog,
  argumentsMap.routes,
  "route",
  authenticated ? protectedRouteNames : publicRouteNames,
);
const viewports = select(
  viewportCatalog,
  argumentsMap.viewports,
  "viewport",
  Object.keys(viewportCatalog),
);
const fullPage = argumentsMap.fullPage !== "false";
const saveScreenshots = argumentsMap.screenshots !== "false";

await mkdir(outputDirectory, { recursive: true });

const browser = await chromium.launch();
const results = [];
let authenticatedStorage;

async function verificationLink(request, mailpitUrl, email) {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const search = await request.get(`${mailpitUrl}/api/v1/search`, {
      params: { query: `to:${email}` },
    });
    if (search.ok()) {
      const body = await search.json();
      const messageId = body.messages?.[0]?.ID;
      if (messageId) {
        const message = await request.get(
          `${mailpitUrl}/view/${encodeURIComponent(messageId)}.txt`,
        );
        if (message.ok()) {
          const link = (await message.text()).match(
            /https?:\/\/[^\s<>]+\/verify-email#token=[A-Za-z0-9._~-]+/,
          )?.[0];
          if (link) return link;
        }
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Verification email did not arrive for ${email}.`);
}

async function bootstrapAuthenticatedStorage() {
  const context = await browser.newContext({
    baseURL: authBaseUrl,
    colorScheme: "light",
    reducedMotion: "reduce",
    viewport: { width: 1024, height: 900 },
  });
  const page = await context.newPage();
  const email = `visual-qa-${randomUUID()}@e2e.invalid.example.com`;
  const password = `${randomUUID()}-aA1!`;
  const mailpitUrl = argumentsMap.mailpitUrl ?? "http://localhost:8025";

  try {
    await page.goto("/register");
    await page.getByLabel("Name").fill("Visual QA Account");
    await page.getByLabel("Email address").fill(email);
    const passwordField = page.getByLabel("Password", { exact: true });
    await passwordField.fill(password);
    await passwordField.press("Enter");
    await page
      .getByRole("heading", { name: "Check your email" })
      .waitFor({ state: "visible" });

    const link = new URL(
      await verificationLink(context.request, mailpitUrl, email),
    );
    await page.goto(`${link.pathname}${link.hash}`);
    await page
      .getByRole("heading", { name: "Email verified" })
      .waitFor({ state: "visible" });
    await page.getByRole("link", { name: "Continue to sign in" }).click();
    await page.getByLabel("Email address").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.waitForURL(/\/(dashboard|onboarding)$/);

    await page.goto("/onboarding");
    const saveProfile = page.getByRole("button", {
      name: "Save and continue",
    });
    if (await saveProfile.isVisible()) {
      await saveProfile.click();
      await page
        .getByRole("button", { name: "Continue without a resume" })
        .click();
      await page
        .getByRole("button", { name: "Continue to preferences" })
        .click();
      await page.getByRole("button", { name: "Finish onboarding" }).click();
      await page.waitForURL(/\/dashboard$/);
    }

    return await context.storageState();
  } finally {
    await context.close();
  }
}

try {
  if (authenticated) {
    authenticatedStorage = await bootstrapAuthenticatedStorage();
  }
  for (const [viewportName, viewport] of viewports) {
    const context = await browser.newContext({
      baseURL: baseUrl,
      colorScheme: "light",
      reducedMotion: "reduce",
      storageState: authenticatedStorage,
      viewport,
    });
    await context.addInitScript(() => {
      globalThis.__rezumiVisualQa = { events: [], layoutShifts: [], lcp: [] };
      try {
        new PerformanceObserver((list) => {
          globalThis.__rezumiVisualQa.lcp.push(...list.getEntries());
        }).observe({ buffered: true, type: "largest-contentful-paint" });
        new PerformanceObserver((list) => {
          globalThis.__rezumiVisualQa.layoutShifts.push(...list.getEntries());
        }).observe({ buffered: true, type: "layout-shift" });
        new PerformanceObserver((list) => {
          globalThis.__rezumiVisualQa.events.push(...list.getEntries());
        }).observe({ durationThreshold: 16, type: "event" });
      } catch {
        // A missing observer is reported as a null lab metric below.
      }
    });

    for (const [routeName, route] of routes) {
      const page = await context.newPage();
      const consoleErrors = [];
      const pageErrors = [];
      page.on("console", (message) => {
        if (message.type() === "error") consoleErrors.push(message.text());
      });
      page.on("pageerror", (error) => pageErrors.push(error.message));

      const response = await page.goto(new URL(route, baseUrl).toString(), {
        waitUntil: "networkidle",
      });
      await page.locator("main").first().waitFor({ state: "visible" });

      const layout = await page.evaluate(() => ({
        bodyWidth: document.body.scrollWidth,
        documentWidth: document.documentElement.scrollWidth,
        reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)")
          .matches,
        viewportWidth: window.innerWidth,
      }));

      await page.keyboard.press("Tab");
      await page.waitForTimeout(100);
      const focused = await page.evaluate(() => ({
        name:
          document.activeElement?.getAttribute("aria-label") ??
          document.activeElement?.textContent?.trim() ??
          "",
        tag: document.activeElement?.tagName ?? "",
      }));
      await page.keyboard.press("Tab");
      const openNavigation = page.getByRole("button", {
        name: /^Open (application navigation|navigation menu)$/,
      });
      if (
        (await openNavigation.count()) > 0 &&
        (await openNavigation.first().isVisible())
      ) {
        await openNavigation.first().click();
        const closeNavigation = page.getByRole("button", {
          name: /^Close (application navigation|navigation menu)$/,
        });
        if (
          (await closeNavigation.count()) > 0 &&
          (await closeNavigation.first().isVisible())
        ) {
          await closeNavigation.first().click();
        } else {
          await page.keyboard.press("Escape");
        }
        await page.waitForTimeout(100);
      }
      const performanceMetrics = await page.evaluate(() => {
        const captured = globalThis.__rezumiVisualQa ?? {
          events: [],
          layoutShifts: [],
          lcp: [],
        };
        const eventEntries = captured.events.filter(
          (entry) => entry.interactionId > 0,
        );
        const scriptEntries = performance
          .getEntriesByType("resource")
          .filter(
            (entry) =>
              entry.initiatorType === "script" ||
              new URL(entry.name).pathname.endsWith(".js"),
          );
        const lcpEntry = captured.lcp.at(-1);
        return {
          cls: captured.layoutShifts
            .filter((entry) => !entry.hadRecentInput)
            .reduce((total, entry) => total + entry.value, 0),
          interactionEventCount: eventEntries.length,
          interactionMaxDurationMs:
            eventEntries.length > 0
              ? Math.max(...eventEntries.map((entry) => entry.duration))
              : 0,
          lcpMs: lcpEntry?.startTime ?? null,
          scriptEncodedBytes: scriptEntries.reduce(
            (total, entry) => total + (entry.encodedBodySize || 0),
            0,
          ),
          scriptTransferBytes: scriptEntries.reduce(
            (total, entry) => total + (entry.transferSize || 0),
            0,
          ),
        };
      });

      const screenshot = saveScreenshots
        ? `${routeName}-${viewportName}.png`
        : null;
      if (screenshot) {
        await page.screenshot({
          animations: "disabled",
          fullPage,
          path: path.join(outputDirectory, screenshot),
        });
      }

      results.push({
        consoleErrors,
        focused,
        horizontalOverflow:
          layout.documentWidth > layout.viewportWidth + 1 ||
          layout.bodyWidth > layout.viewportWidth + 1,
        layout,
        pageErrors,
        performanceMetrics,
        route,
        routeName,
        screenshot,
        status: response?.status() ?? null,
        url: page.url(),
        viewport,
        viewportName,
      });

      await page.close();
    }

    await context.close();
  }
} finally {
  await browser.close();
}

const reportPath = path.join(outputDirectory, "qa-results.json");
await writeFile(reportPath, `${JSON.stringify(results, null, 2)}\n`, "utf8");

const failures = results.filter(
  (result) =>
    result.status === null ||
    result.status >= 400 ||
    result.horizontalOverflow ||
    !result.layout.reducedMotion ||
    result.consoleErrors.length > 0 ||
    result.pageErrors.length > 0 ||
    (result.performanceMetrics.lcpMs !== null &&
      result.performanceMetrics.lcpMs > 2500) ||
    result.performanceMetrics.cls > 0.1 ||
    (result.performanceMetrics.interactionMaxDurationMs !== null &&
      result.performanceMetrics.interactionMaxDurationMs > 200),
);

console.log(
  JSON.stringify(
    {
      captures: results.length,
      failures: failures.map((result) => ({
        consoleErrors: result.consoleErrors,
        horizontalOverflow: result.horizontalOverflow,
        pageErrors: result.pageErrors,
        performanceMetrics: result.performanceMetrics,
        route: result.route,
        status: result.status,
        viewport: result.viewportName,
      })),
      outputDirectory,
      reportPath,
    },
    null,
    2,
  ),
);

if (failures.length > 0) process.exitCode = 1;
