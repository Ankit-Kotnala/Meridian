import type { GeneratedApiPath } from "@/shared/api/api-path";
import { buildApiQueryString } from "@/shared/api/api-query-string";

function path(value: string): GeneratedApiPath {
  if (!value.startsWith("/api/v1/") || /[\s#]/.test(value)) {
    throw new Error("Invalid Networking API path.");
  }
  return value as GeneratedApiPath;
}

function resource(base: string, id: string): GeneratedApiPath {
  if (!id) throw new Error("A resource identifier is required.");
  return path(`${base}/${encodeURIComponent(id)}`);
}

export const networkingPaths = {
  applications: path("/api/v1/applications"),
  consent: (contactId: string) =>
    path(
      `/api/v1/networking/contacts/${encodeURIComponent(contactId)}/consent`,
    ),
  consentGrants: (contactId: string) =>
    path(
      `/api/v1/networking/contacts/${encodeURIComponent(
        contactId,
      )}/consent/grants`,
    ),
  consentWithdrawals: (contactId: string) =>
    path(
      `/api/v1/networking/contacts/${encodeURIComponent(
        contactId,
      )}/consent/withdrawals`,
    ),
  contact: (contactId: string) =>
    resource("/api/v1/networking/contacts", contactId),
  contacts: path("/api/v1/networking/contacts"),
  interactions: (contactId: string) =>
    path(
      `/api/v1/networking/contacts/${encodeURIComponent(
        contactId,
      )}/interactions`,
    ),
  notes: (contactId: string) =>
    path(`/api/v1/networking/contacts/${encodeURIComponent(contactId)}/notes`),
  organization: (organizationId: string) =>
    resource("/api/v1/networking/organizations", organizationId),
  organizations: path("/api/v1/networking/organizations"),
  referral: (referralId: string) =>
    resource("/api/v1/networking/referrals", referralId),
  referrals: (contactId: string) =>
    path(
      `/api/v1/networking/contacts/${encodeURIComponent(contactId)}/referrals`,
    ),
  reminder: (reminderId: string) =>
    resource("/api/v1/networking/reminders", reminderId),
  reminderActions: (reminderId: string) =>
    path(
      `/api/v1/networking/reminders/${encodeURIComponent(reminderId)}/actions`,
    ),
  reminderExecutions: path("/api/v1/networking/reminders/executions"),
  reminderExecution: (reminderId: string) =>
    path(
      `/api/v1/networking/reminders/${encodeURIComponent(
        reminderId,
      )}/execution`,
    ),
  reminders: (contactId: string) =>
    path(
      `/api/v1/networking/contacts/${encodeURIComponent(contactId)}/reminders`,
    ),
  dueReminders: path("/api/v1/networking/reminders/due"),
  template: (templateId: string) =>
    resource("/api/v1/networking/templates", templateId),
  templates: path("/api/v1/networking/templates"),
} as const;

export function withNetworkingQuery(
  base: GeneratedApiPath,
  values: Parameters<typeof buildApiQueryString>[0],
): GeneratedApiPath {
  return path(`${base}${buildApiQueryString(values)}`);
}
