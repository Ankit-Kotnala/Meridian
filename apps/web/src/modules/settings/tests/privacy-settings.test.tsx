import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { PrivacySettings } from "../views/privacy-settings";

const api = vi.hoisted(() => ({
  createAccountExportDownload: vi.fn(),
  getSettingsCapabilities: vi.fn(),
  requestAccountDeletion: vi.fn(),
  requestAccountExport: vi.fn(),
  waitForAccountOperation: vi.fn(),
}));

vi.mock("../api/settings-api", () => api);
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function close() {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
});

const capabilities = {
  accountDeletionAvailable: true,
  accountExportAvailable: true,
  accountResumeRetention: "untilDeleted",
  billingAvailable: false,
  googleConnected: false,
  googleOauthAvailable: false,
  guestResumeRetentionHours: 24,
  hasPassword: true,
  reminderPreferencesAvailable: true,
  scheduledNotificationDeliveryAvailable: false,
};

const queuedExport = {
  artifactExpiresAt: null,
  artifactSha256: null,
  artifactSizeBytes: null,
  attempts: 0,
  blockedReason: null,
  completedAt: null,
  id: "00000000-0000-4000-8000-000000000901",
  kind: "export",
  maxAttempts: 5,
  operationToken: "t".repeat(80),
  requestedAt: "2026-07-27T04:00:00Z",
  status: "queued",
  updatedAt: "2026-07-27T04:00:00Z",
};

const completedExport = {
  ...queuedExport,
  artifactExpiresAt: "2026-07-28T04:00:00Z",
  artifactSha256: "a".repeat(64),
  artifactSizeBytes: 2048,
  attempts: 1,
  completedAt: "2026-07-27T04:00:02Z",
  status: "succeeded",
  updatedAt: "2026-07-27T04:00:02Z",
};

const queuedDeletion = {
  ...queuedExport,
  id: "00000000-0000-4000-8000-000000000902",
  kind: "deletion",
  operationToken: "d".repeat(80),
};

const blockedDeletion = {
  ...queuedDeletion,
  attempts: 1,
  blockedReason: "organization_ownership_transfer_required",
  completedAt: "2026-07-27T04:00:03Z",
  status: "blocked",
  updatedAt: "2026-07-27T04:00:03Z",
};

describe("privacy settings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getSettingsCapabilities.mockResolvedValue(capabilities);
    api.requestAccountExport.mockResolvedValue(queuedExport);
    api.requestAccountDeletion.mockResolvedValue(queuedDeletion);
    api.waitForAccountOperation.mockResolvedValue(completedExport);
    api.createAccountExportDownload.mockResolvedValue({
      downloadUrl: "https://downloads.invalid/account-export.zip",
      expiresInSeconds: 120,
    });
  });

  it("requests, tracks, and exposes only a short-lived completed export", async () => {
    render(<PrivacySettings />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Request export" }),
    );

    expect(await screen.findByText("Account export completed")).toBeVisible();
    expect(api.requestAccountExport).toHaveBeenCalledWith(
      expect.stringMatching(/^settings-export:/),
    );
    expect(api.waitForAccountOperation).toHaveBeenCalledWith(
      queuedExport,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Create download link" }),
    );
    const link = await screen.findByRole("link", {
      name: "Download account export",
    });
    expect(link).toHaveAttribute(
      "href",
      "https://downloads.invalid/account-export.zip",
    );
    expect(api.createAccountExportDownload).toHaveBeenCalledWith(
      queuedExport.id,
      queuedExport.operationToken,
    );
  });

  it("requires destructive confirmation and explains a safe ownership block", async () => {
    api.waitForAccountOperation.mockResolvedValue(blockedDeletion);
    render(<PrivacySettings />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Start deletion" }),
    );
    expect(
      screen.getByRole("heading", {
        name: "Delete your CareerOS account?",
      }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Delete account" }));

    expect(await screen.findByText("Operation blocked safely")).toBeVisible();
    expect(
      screen.getByText(/Transfer ownership of every organization/),
    ).toBeVisible();
    expect(api.requestAccountDeletion).toHaveBeenCalledWith(
      expect.stringMatching(/^settings-deletion:/),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Start deletion" }),
      ).toBeEnabled(),
    );
  });

  it("keeps unsupported operations disabled and explains why", async () => {
    api.getSettingsCapabilities.mockResolvedValue({
      ...capabilities,
      accountDeletionAvailable: false,
      accountExportAvailable: false,
    });
    render(<PrivacySettings />);

    expect(await screen.findByText("Export is unavailable")).toBeVisible();
    expect(screen.getByText("Deletion is unavailable")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Request export" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Start deletion" }),
    ).not.toBeInTheDocument();
  });
});
