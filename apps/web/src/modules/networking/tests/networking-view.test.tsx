import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Contact } from "../api/types";
import { NetworkingView } from "../views/networking-view";

const api = vi.hoisted(() => ({
  createContact: vi.fn(),
  createOrganization: vi.fn(),
  createTemplate: vi.fn(),
  deleteOrganization: vi.fn(),
  listDueReminders: vi.fn(),
  listContacts: vi.fn(),
  listOrganizations: vi.fn(),
  listTemplates: vi.fn(),
  resolveReminder: vi.fn(),
  updateOrganization: vi.fn(),
  updateTemplate: vi.fn(),
  ApiRequestError: class extends Error {},
}));

vi.mock("../api/networking-api", () => api);

const contact: Contact = {
  consent: {
    allowsOutreach: false,
    collection: true,
    outreach: false,
    storage: true,
  },
  createdAt: "2026-07-24T10:00:00Z",
  email: "mentor@example.invalid",
  id: "00000000-0000-4000-8000-000000000301",
  lastContactAt: null,
  location: "Remote",
  name: "Example Mentor",
  nextContactAt: null,
  organizationId: null,
  phone: null,
  profileUrl: null,
  referralState: "none",
  relationshipStage: "warm",
  role: "Engineering leader",
  tags: ["mentor"],
  updatedAt: "2026-07-24T10:00:00Z",
  version: 1,
};

describe("Networking view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listContacts.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 50, nextCursor: null },
    });
    api.listOrganizations.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 50, nextCursor: null },
    });
    api.listTemplates.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 100, nextCursor: null },
    });
    api.listDueReminders.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 50, nextCursor: null },
    });
    api.createContact.mockResolvedValue(contact);
  });

  it("requires separate collection and storage attestations when saving a contact", async () => {
    render(<NetworkingView />);

    expect(
      await screen.findByRole("heading", {
        name: "A private, consent-based relationship workspace",
      }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /send|scrape|import/i }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add contact" }));
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: contact.name },
    });
    fireEvent.click(screen.getByLabelText("Collection consent is attested"));
    fireEvent.click(screen.getByLabelText("Storage consent is attested"));
    fireEvent.click(
      screen.getByRole("button", { name: "Save consented contact" }),
    );

    expect(
      await screen.findByText(
        "Example Mentor saved with separate collection, storage, and outreach consent state.",
      ),
    ).toBeVisible();
    expect(api.createContact).toHaveBeenCalledWith(
      expect.objectContaining({
        consent: {
          collectionAttested: true,
          outreachAttested: false,
          policyVersion: "networking-contact-consent/1",
          storageAttested: true,
        },
        name: contact.name,
      }),
      expect.stringMatching(/^networking-web:/),
    );
  });

  it("renders real empty states for all private collections", async () => {
    render(<NetworkingView />);

    expect(
      await screen.findByRole("heading", { name: "No private contacts" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("tab", { name: "Organizations (0)" }));
    expect(
      screen.getByRole("heading", { name: "No organizations" }),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("tab", { name: "Reviewed templates (0)" }),
    );
    expect(
      screen.getByRole("heading", { name: "No reviewed templates" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("tab", { name: "Due reminders (0)" }));
    expect(
      await screen.findByRole("heading", { name: "No due reminders" }),
    ).toBeVisible();
  });
});
