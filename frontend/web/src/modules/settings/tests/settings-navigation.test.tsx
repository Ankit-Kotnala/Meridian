import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SettingsCapabilitiesProvider } from "../components/settings-capabilities-context";
import { SettingsNavigation } from "../components/settings-navigation";

vi.mock("next/navigation", () => ({
  usePathname: () => "/settings/application-answers",
}));

vi.mock("../api/settings-api", () => ({
  getSettingsCapabilities: vi.fn(async () => ({
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
  })),
}));

describe("SettingsNavigation", () => {
  it("includes the application answers destination", async () => {
    render(
      <SettingsCapabilitiesProvider>
        <SettingsNavigation />
      </SettingsCapabilitiesProvider>,
    );

    const answers = await screen.findByRole("link", {
      name: "Application answers",
    });
    expect(answers).toHaveAttribute("href", "/settings/application-answers");
    expect(answers).toHaveAttribute("aria-current", "page");
    expect(
      screen.getByRole("link", { name: "Profile and account" }),
    ).not.toHaveAttribute("aria-current");
  });
});
