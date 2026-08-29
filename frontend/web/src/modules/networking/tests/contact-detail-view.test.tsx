import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  ConsentEvent,
  Contact,
  Reminder,
  ReminderExecution,
} from "../api/types";
import { ContactDetailView } from "../views/contact-detail-view";

const router = vi.hoisted(() => ({
  refresh: vi.fn(),
  replace: vi.fn(),
}));
const api = vi.hoisted(() => ({
  createContactNote: vi.fn(),
  createReferral: vi.fn(),
  createReminder: vi.fn(),
  deleteContact: vi.fn(),
  getConsentHistory: vi.fn(),
  getContact: vi.fn(),
  getReminderExecutions: vi.fn(),
  grantConsent: vi.fn(),
  listContactNotes: vi.fn(),
  listInteractions: vi.fn(),
  listNetworkingApplications: vi.fn(),
  listOrganizations: vi.fn(),
  listReferrals: vi.fn(),
  listReminders: vi.fn(),
  listTemplates: vi.fn(),
  recordInteraction: vi.fn(),
  resolveReminder: vi.fn(),
  updateContact: vi.fn(),
  updateReferral: vi.fn(),
  updateReminder: vi.fn(),
  withdrawConsent: vi.fn(),
  ApiRequestError: class extends Error {},
}));

vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("../api/networking-api", () => api);

const contact: Contact = {
  consent: {
    allowsOutreach: true,
    collection: true,
    outreach: true,
    storage: true,
  },
  createdAt: "2026-07-24T10:00:00Z",
  email: "mentor@example.invalid",
  id: "00000000-0000-4000-8000-000000000401",
  lastContactAt: "2026-07-23T10:00:00Z",
  location: "Remote",
  name: "Example Mentor",
  nextContactAt: "2026-07-26T10:00:00Z",
  organizationId: null,
  phone: null,
  profileUrl: null,
  referralState: "considering",
  relationshipStage: "trusted",
  role: "Engineering leader",
  tags: ["mentor"],
  updatedAt: "2026-07-24T10:00:00Z",
  version: 3,
};

const consentEvent: ConsentEvent = {
  action: "granted",
  contactId: contact.id,
  id: "00000000-0000-4000-8000-000000000402",
  occurredAt: "2026-07-24T10:00:00Z",
  policyVersion: "networking-contact-consent/1",
  purpose: "outreach",
  sequence: 3,
};

const reminder: Reminder = {
  contactId: contact.id,
  createdAt: "2026-07-24T10:00:00Z",
  dueAt: "2026-07-25T10:00:00Z",
  id: "00000000-0000-4000-8000-000000000403",
  maxAttempts: 5,
  recurrenceDays: null,
  status: "active",
  title: "Review follow-up plan",
  updatedAt: "2026-07-24T10:00:00Z",
  version: 1,
};

const execution: ReminderExecution = {
  attemptCount: 5,
  lastErrorCode: "LOCAL_MATERIALIZATION_LIMIT",
  maxAttempts: 5,
  occurrenceId: "00000000-0000-4000-8000-000000000404",
  occurrenceNumber: 1,
  occurrenceStatus: "dead_letter",
  queueStatus: "dead_letter",
  scheduledFor: reminder.dueAt,
};

describe("private contact detail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getContact.mockResolvedValue(contact);
    api.getConsentHistory.mockResolvedValue({
      current: contact.consent,
      events: [consentEvent],
      page: { hasMore: false, limit: 100, nextCursor: null },
    });
    api.listContactNotes.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 100, nextCursor: null },
    });
    api.listInteractions.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 100, nextCursor: null },
    });
    api.listReferrals.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 100, nextCursor: null },
    });
    api.listReminders.mockResolvedValue({
      data: [reminder],
      page: { hasMore: false, limit: 100, nextCursor: null },
    });
    api.getReminderExecutions.mockResolvedValue({
      data: [{ execution, reminderId: reminder.id }],
    });
    api.listTemplates.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 100, nextCursor: null },
    });
    api.listOrganizations.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 100, nextCursor: null },
    });
    api.listNetworkingApplications.mockResolvedValue({
      data: [],
      page: { hasMore: false, limit: 100, nextCursor: null },
    });
  });

  it("shows purpose-scoped consent and bounded append-only history", async () => {
    render(<ContactDetailView contactId={contact.id} />);

    expect(
      await screen.findByRole("heading", { name: contact.name }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("tab", { name: /^Consent history/ }));
    expect(
      await screen.findByText("Append-only consent history"),
    ).toBeVisible();
    expect(
      screen.getByText("Sequence 3 · Policy networking-contact-consent/1 ·", {
        exact: false,
      }),
    ).toBeVisible();
  });

  it("shows honest local dead-letter state and redacted failure code without delivery controls", async () => {
    render(<ContactDetailView contactId={contact.id} />);
    await screen.findByRole("heading", { name: contact.name });
    fireEvent.click(screen.getByRole("tab", { name: /^Local reminders/ }));

    expect(await screen.findByText("Queue: Dead Letter")).toBeVisible();
    expect(
      screen.getByText("Safe failure code:", { exact: false }),
    ).toBeVisible();
    expect(screen.getByText("LOCAL_MATERIALIZATION_LIMIT")).toBeVisible();
    expect(screen.getByText(/No delivery action exists/i)).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /send|email|message|push/i }),
    ).not.toBeInTheDocument();
    expect(api.getReminderExecutions).toHaveBeenCalledTimes(1);
    expect(api.getReminderExecutions).toHaveBeenCalledWith(
      [reminder.id],
      expect.any(AbortSignal),
    );
  });

  it("warns that storage withdrawal is destructive and leaves the redacted contact route", async () => {
    api.withdrawConsent.mockResolvedValue({
      ...contact,
      consent: {
        allowsOutreach: false,
        collection: false,
        outreach: false,
        storage: false,
      },
      email: null,
      location: null,
      name: "[deleted]",
      role: null,
      tags: [],
      version: 4,
    });
    render(<ContactDetailView contactId={contact.id} />);
    await screen.findByRole("heading", { name: contact.name });
    fireEvent.click(screen.getByRole("tab", { name: /^Consent history/ }));
    await screen.findByText("Append-only consent history");

    expect(
      screen.getByText(
        /Withdrawing collection or storage permanently redacts/i,
      ),
    ).toBeVisible();
    const submit = screen.getByRole("button", { name: "Record withdrawal" });
    const form = submit.closest("form");
    expect(form).not.toBeNull();
    fireEvent.change(within(form!).getByLabelText("Purpose"), {
      target: { value: "storage" },
    });
    fireEvent.submit(form!);

    await waitFor(() =>
      expect(router.replace).toHaveBeenCalledWith("/networking"),
    );
    expect(router.refresh).toHaveBeenCalled();
    expect(api.withdrawConsent).toHaveBeenCalledWith(
      contact,
      {
        policyVersion: "networking-contact-consent/1",
        purpose: "storage",
      },
      expect.any(String),
    );
    expect(api.getContact).toHaveBeenCalledTimes(1);
  });
});
