import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApplicationProfilePanel } from "../components/application-profile-panel";

const api = vi.hoisted(() => ({
  getApplicationProfile: vi.fn(),
  upsertApplicationProfile: vi.fn(),
}));

vi.mock("../api/applications-api", () => api);

describe("ApplicationProfilePanel", () => {
  beforeEach(() => {
    api.getApplicationProfile.mockReset();
    api.upsertApplicationProfile.mockReset();
    api.getApplicationProfile.mockResolvedValue(null);
    api.upsertApplicationProfile.mockImplementation(async (input) => ({
      compensationCurrency: input.compensationCurrency,
      compensationMax: input.compensationMax,
      compensationMin: input.compensationMin,
      createdAt: "2026-09-01T00:00:00Z",
      id: "00000000-0000-4000-8000-000000000301",
      noticePeriodDays: input.noticePeriodDays,
      preferredLocations: input.preferredLocations,
      profileLinks: input.profileLinks,
      updatedAt: "2026-09-01T00:00:00Z",
      version: 1,
      voluntaryDisclosures: input.voluntaryDisclosures,
      workAuthorization: input.workAuthorization,
    }));
  });

  it("saves disability and veteran answers on the owner Application Profile", async () => {
    render(<ApplicationProfilePanel />);

    expect(
      await screen.findByRole("heading", { name: "Application answers" }),
    ).toBeVisible();

    fireEvent.change(screen.getByLabelText("Disability status (Section 503)"), {
      target: {
        value:
          "Yes, I have a disability, or have a history/record of having a disability",
      },
    });
    fireEvent.change(screen.getByLabelText("Veteran status (VEVRAA)"), {
      target: {
        value: "I am not a protected veteran",
      },
    });
    fireEvent.change(screen.getByLabelText("Race / ethnicity (EEO-1)"), {
      target: { value: "Asian" },
    });
    fireEvent.click(
      screen.getByLabelText(
        "These answers are mine. Save them on this account for Apply for me.",
      ),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Save application answers" }),
    );

    await waitFor(() => {
      expect(api.upsertApplicationProfile).toHaveBeenCalledTimes(1);
    });
    expect(api.upsertApplicationProfile).toHaveBeenCalledWith(
      expect.objectContaining({
        voluntaryDisclosures: expect.objectContaining({
          disability_status:
            "Yes, I have a disability, or have a history/record of having a disability",
          questionnaire_ack: "acknowledged",
          race_ethnicity: "Asian",
          veteran_status: "I am not a protected veteran",
        }),
        workAuthorization: null,
      }),
    );
    expect(await screen.findByText(/Saved for this account/i)).toBeVisible();
  });

  it("does not save until the owner acknowledges storage", async () => {
    render(<ApplicationProfilePanel />);
    await screen.findByRole("heading", { name: "Application answers" });
    fireEvent.click(
      screen.getByRole("button", { name: "Save application answers" }),
    );
    expect(api.upsertApplicationProfile).not.toHaveBeenCalled();
    expect(
      screen.getByText(
        "Confirm that these answers are yours and will be stored for Apply for me.",
      ),
    ).toBeVisible();
  });

  it("keeps a previously saved disclosure that is not in the catalog", async () => {
    api.getApplicationProfile.mockResolvedValue({
      compensationCurrency: "USD",
      compensationMax: null,
      compensationMin: null,
      createdAt: "2026-09-01T00:00:00Z",
      id: "00000000-0000-4000-8000-000000000301",
      noticePeriodDays: null,
      preferredLocations: [],
      profileLinks: [],
      updatedAt: "2026-09-01T00:00:00Z",
      version: 1,
      voluntaryDisclosures: { veteran_status: "prefer_not_to_say" },
      workAuthorization: "US citizen",
    });
    render(<ApplicationProfilePanel />);
    expect(
      await screen.findByRole("heading", { name: "Application answers" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Veteran status (VEVRAA)")).toHaveValue(
      "prefer_not_to_say",
    );
    expect(screen.getByLabelText("Work authorization")).toHaveValue(
      "US citizen",
    );
  });
});
