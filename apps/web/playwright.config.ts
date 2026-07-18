import { defineConfig, devices } from "@playwright/test";

const fullStack = process.env.PLAYWRIGHT_E2E_MODE === "full-stack";
const externalServer = process.env.PLAYWRIGHT_EXTERNAL_SERVER === "1";
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000";
const localPort = new URL(baseURL).port || "3000";

export default defineConfig({
  testDir: "./e2e",
  testIgnore: fullStack ? [] : ["**/*-journey.spec.ts"],
  fullyParallel: !fullStack,
  forbidOnly: Boolean(process.env.CI),
  preserveOutput: fullStack ? "never" : "always",
  retries: process.env.CI ? 2 : 0,
  ...(process.env.CI || fullStack ? { workers: 1 } : {}),
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL,
    trace: fullStack ? "off" : "on-first-retry",
    screenshot: fullStack ? "off" : "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] } },
  ],
  ...(externalServer
    ? {}
    : {
        webServer: {
          command: `pnpm dev --hostname 127.0.0.1 --port ${localPort}`,
          url: `${baseURL}/api/health`,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        },
      }),
});
