import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NotificationSettings } from "../views/notification-settings";
import { SecuritySettings } from "../views/security-settings";

const replace = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh, replace }),
}));

const capabilities = {
  accountDeletionAvailable: false,
  accountExportAvailable: false,
  accountResumeRetention: "untilDeleted",
  billingAvailable: false,
  googleConnected: false,
  googleOauthAvailable: false,
  guestResumeRetentionHours: 24,
  hasPassword: true,
  reminderPreferencesAvailable: true,
  scheduledNotificationDeliveryAvailable: false,
};

function json(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

describe("account settings", () => {
  beforeEach(() => {
    document.cookie = "rezumi_csrf=session-csrf; Path=/";
  });

  afterEach(() => {
    document.cookie = "rezumi_csrf=; Max-Age=0; Path=/";
    replace.mockReset();
    refresh.mockReset();
    vi.unstubAllGlobals();
  });

  it("changes a password through the protected endpoint and shows redacted activity", async () => {
    const fetchMock = vi.fn(
      async (input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/v1/settings")) return json(capabilities);
        if (url.endsWith("/api/v1/security-activity")) {
          return json({
            data: [
              {
                currentSession: true,
                eventType: "auth.login",
                id: "00000000-0000-4000-8000-000000000001",
                occurredAt: "2026-07-26T09:00:00Z",
                outcome: "success",
              },
            ],
          });
        }
        if (
          url.endsWith("/api/v1/auth/change-password") &&
          init?.method === "POST"
        ) {
          return new Response(null, { status: 204 });
        }
        throw new Error(`Unexpected request: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<SecuritySettings />);

    expect(await screen.findByText("Account sign-in")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Current password"), {
      target: { value: "current test-only password" },
    });
    fireEvent.change(screen.getByLabelText("New password"), {
      target: { value: "replacement test-only password" },
    });
    fireEvent.change(screen.getByLabelText("Confirm new password"), {
      target: { value: "replacement test-only password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/login?passwordChanged=1"),
    );
    const mutation = fetchMock.mock.calls.find(([url]) =>
      String(url).endsWith("/api/v1/auth/change-password"),
    );
    expect(JSON.parse(String(mutation?.[1]?.body))).toEqual({
      currentPassword: "current test-only password",
      newPassword: "replacement test-only password",
    });
  });

  it("stores reminder preferences while disclosing unavailable delivery", async () => {
    const fetchMock = vi.fn(
      async (input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/v1/settings")) return json(capabilities);
        if (
          url.endsWith("/api/v1/achievements/reminder-preferences") &&
          (!init?.method || init.method === "GET")
        ) {
          return json({
            dayOfMonth: null,
            enabled: false,
            timezone: "Asia/Kolkata",
            updatedAt: "2026-07-26T09:00:00Z",
            version: 1,
          });
        }
        if (
          url.endsWith("/api/v1/achievements/reminder-preferences") &&
          init?.method === "PATCH"
        ) {
          return json({
            dayOfMonth: 12,
            enabled: true,
            timezone: "Asia/Kolkata",
            updatedAt: "2026-07-26T09:05:00Z",
            version: 2,
          });
        }
        throw new Error(`Unexpected request: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<NotificationSettings />);

    expect(
      await screen.findByText("Scheduled delivery is not configured"),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /Enable monthly capture reminders/,
      }),
    );
    fireEvent.change(screen.getByLabelText("Day of month"), {
      target: { value: "12" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save reminder preferences" }),
    );

    expect(
      await screen.findByText("Reminder preferences saved."),
    ).toBeVisible();
    const mutation = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/api/v1/achievements/reminder-preferences") &&
        init?.method === "PATCH",
    );
    expect(JSON.parse(String(mutation?.[1]?.body))).toEqual({
      dayOfMonth: 12,
      enabled: true,
      timezone: "Asia/Kolkata",
    });
  });
});
