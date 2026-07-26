"use client";

import {
  ApiRequestError,
  apiMutation,
  apiQuery,
} from "@/shared/api/browser-request";

import { networkingPaths, withNetworkingQuery } from "./paths";
import type {
  ApplicationPage,
  ConsentChangeInput,
  ConsentHistory,
  Contact,
  ContactCreateInput,
  ContactNote,
  ContactNoteCreateInput,
  ContactNotePage,
  ContactPage,
  ContactReferralState,
  ContactUpdateInput,
  DueReminderPage,
  Interaction,
  InteractionCreateInput,
  InteractionPage,
  NetworkingTemplate,
  NetworkingTemplatePage,
  Organization,
  OrganizationCreateInput,
  OrganizationPage,
  OrganizationUpdateInput,
  PageOptions,
  Referral,
  ReferralCreateInput,
  ReferralPage,
  ReferralUpdateInput,
  RelationshipStage,
  Reminder,
  ReminderCreateInput,
  ReminderExecutionBatch,
  ReminderPage,
  ReminderResolutionInput,
  ReminderUpdateInput,
  TemplateCreateInput,
  TemplateUpdateInput,
} from "./types";

function mutationHeaders(
  version?: number,
  idempotencyKey?: string,
): HeadersInit {
  return {
    ...(version === undefined ? {} : { "If-Match": `"${version}"` }),
    ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
  };
}

async function query(
  path: Parameters<typeof apiQuery>[0],
  signal?: AbortSignal,
) {
  return apiQuery(path, {
    retryAfterRefresh: true,
    ...(signal ? { signal } : {}),
  });
}

async function mutate(
  path: Parameters<typeof apiMutation>[0],
  init: Parameters<typeof apiMutation>[1],
) {
  return apiMutation(path, init, { csrf: "session" });
}

export async function listNetworkingApplications(
  options: {
    cursor?: string;
    limit?: number;
    q?: string;
    signal?: AbortSignal;
  } = {},
): Promise<ApplicationPage> {
  const response = await query(
    withNetworkingQuery(networkingPaths.applications, {
      cursor: options.cursor,
      limit: options.limit ?? 50,
      q: options.q || undefined,
    }),
    options.signal,
  );
  return (await response.json()) as ApplicationPage;
}

export async function listOrganizations(
  options: PageOptions & { q?: string; tag?: string } = {},
): Promise<OrganizationPage> {
  const response = await query(
    withNetworkingQuery(networkingPaths.organizations, {
      cursor: options.cursor,
      limit: options.limit ?? 50,
      q: options.q || undefined,
      tag: options.tag || undefined,
    }),
    options.signal,
  );
  return (await response.json()) as OrganizationPage;
}

export async function getOrganization(
  organizationId: string,
  signal?: AbortSignal,
): Promise<Organization> {
  const response = await query(
    networkingPaths.organization(organizationId),
    signal,
  );
  return (await response.json()) as Organization;
}

export async function createOrganization(
  input: OrganizationCreateInput,
  idempotencyKey: string,
): Promise<Organization> {
  const response = await mutate(networkingPaths.organizations, {
    body: JSON.stringify(input),
    headers: mutationHeaders(undefined, idempotencyKey),
    method: "POST",
  });
  return (await response.json()) as Organization;
}

export async function updateOrganization(
  organization: Pick<Organization, "id" | "version">,
  input: OrganizationUpdateInput,
  idempotencyKey: string,
): Promise<Organization> {
  const response = await mutate(networkingPaths.organization(organization.id), {
    body: JSON.stringify(input),
    headers: mutationHeaders(organization.version, idempotencyKey),
    method: "PATCH",
  });
  return (await response.json()) as Organization;
}

export async function deleteOrganization(
  organization: Pick<Organization, "id" | "version">,
  idempotencyKey: string,
): Promise<void> {
  await mutate(networkingPaths.organization(organization.id), {
    headers: mutationHeaders(organization.version, idempotencyKey),
    method: "DELETE",
  });
}

export async function listContacts(
  options: PageOptions & {
    organizationId?: string;
    outreachConsent?: boolean;
    q?: string;
    referralState?: ContactReferralState | "";
    relationshipStage?: RelationshipStage | "";
    tag?: string;
  } = {},
): Promise<ContactPage> {
  const response = await query(
    withNetworkingQuery(networkingPaths.contacts, {
      cursor: options.cursor,
      limit: options.limit ?? 50,
      organizationId: options.organizationId,
      outreachConsent: options.outreachConsent,
      q: options.q || undefined,
      referralState: options.referralState || undefined,
      relationshipStage: options.relationshipStage || undefined,
      tag: options.tag || undefined,
    }),
    options.signal,
  );
  return (await response.json()) as ContactPage;
}

export async function getContact(
  contactId: string,
  signal?: AbortSignal,
): Promise<Contact> {
  const response = await query(networkingPaths.contact(contactId), signal);
  return (await response.json()) as Contact;
}

export async function createContact(
  input: ContactCreateInput,
  idempotencyKey: string,
): Promise<Contact> {
  const response = await mutate(networkingPaths.contacts, {
    body: JSON.stringify(input),
    headers: mutationHeaders(undefined, idempotencyKey),
    method: "POST",
  });
  return (await response.json()) as Contact;
}

export async function updateContact(
  contact: Pick<Contact, "id" | "version">,
  input: ContactUpdateInput,
  idempotencyKey: string,
): Promise<Contact> {
  const response = await mutate(networkingPaths.contact(contact.id), {
    body: JSON.stringify(input),
    headers: mutationHeaders(contact.version, idempotencyKey),
    method: "PATCH",
  });
  return (await response.json()) as Contact;
}

export async function deleteContact(
  contact: Pick<Contact, "id" | "version">,
  idempotencyKey: string,
): Promise<void> {
  await mutate(networkingPaths.contact(contact.id), {
    headers: mutationHeaders(contact.version, idempotencyKey),
    method: "DELETE",
  });
}

export async function getConsentHistory(
  contactId: string,
  options: PageOptions = {},
): Promise<ConsentHistory> {
  const response = await query(
    withNetworkingQuery(networkingPaths.consent(contactId), {
      cursor: options.cursor,
      limit: options.limit ?? 100,
    }),
    options.signal,
  );
  return (await response.json()) as ConsentHistory;
}

export async function grantConsent(
  contact: Pick<Contact, "id" | "version">,
  input: ConsentChangeInput,
  idempotencyKey: string,
): Promise<Contact> {
  const response = await mutate(networkingPaths.consentGrants(contact.id), {
    body: JSON.stringify(input),
    headers: mutationHeaders(contact.version, idempotencyKey),
    method: "POST",
  });
  return (await response.json()) as Contact;
}

export async function withdrawConsent(
  contact: Pick<Contact, "id" | "version">,
  input: ConsentChangeInput,
  idempotencyKey: string,
): Promise<Contact> {
  const response = await mutate(
    networkingPaths.consentWithdrawals(contact.id),
    {
      body: JSON.stringify(input),
      headers: mutationHeaders(contact.version, idempotencyKey),
      method: "POST",
    },
  );
  return (await response.json()) as Contact;
}

export async function listContactNotes(
  contactId: string,
  options: PageOptions = {},
): Promise<ContactNotePage> {
  const response = await query(
    withNetworkingQuery(networkingPaths.notes(contactId), {
      cursor: options.cursor,
      limit: options.limit ?? 100,
    }),
    options.signal,
  );
  return (await response.json()) as ContactNotePage;
}

export async function createContactNote(
  contactId: string,
  input: ContactNoteCreateInput,
  idempotencyKey: string,
): Promise<ContactNote> {
  const response = await mutate(networkingPaths.notes(contactId), {
    body: JSON.stringify(input),
    headers: mutationHeaders(undefined, idempotencyKey),
    method: "POST",
  });
  return (await response.json()) as ContactNote;
}

export async function listInteractions(
  contactId: string,
  options: PageOptions = {},
): Promise<InteractionPage> {
  const response = await query(
    withNetworkingQuery(networkingPaths.interactions(contactId), {
      cursor: options.cursor,
      limit: options.limit ?? 100,
    }),
    options.signal,
  );
  return (await response.json()) as InteractionPage;
}

export async function recordInteraction(
  contact: Pick<Contact, "id" | "version">,
  input: InteractionCreateInput,
  idempotencyKey: string,
): Promise<Interaction> {
  const response = await mutate(networkingPaths.interactions(contact.id), {
    body: JSON.stringify(input),
    headers: mutationHeaders(contact.version, idempotencyKey),
    method: "POST",
  });
  return (await response.json()) as Interaction;
}

export async function listReferrals(
  contactId: string,
  options: PageOptions = {},
): Promise<ReferralPage> {
  const response = await query(
    withNetworkingQuery(networkingPaths.referrals(contactId), {
      cursor: options.cursor,
      limit: options.limit ?? 100,
    }),
    options.signal,
  );
  return (await response.json()) as ReferralPage;
}

export async function createReferral(
  contact: Pick<Contact, "id" | "version">,
  input: ReferralCreateInput,
  idempotencyKey: string,
): Promise<Referral> {
  const response = await mutate(networkingPaths.referrals(contact.id), {
    body: JSON.stringify(input),
    headers: mutationHeaders(contact.version, idempotencyKey),
    method: "POST",
  });
  return (await response.json()) as Referral;
}

export async function updateReferral(
  referral: Pick<Referral, "id" | "version">,
  input: ReferralUpdateInput,
  idempotencyKey: string,
): Promise<Referral> {
  const response = await mutate(networkingPaths.referral(referral.id), {
    body: JSON.stringify(input),
    headers: mutationHeaders(referral.version, idempotencyKey),
    method: "PATCH",
  });
  return (await response.json()) as Referral;
}

export async function listTemplates(
  options: PageOptions = {},
): Promise<NetworkingTemplatePage> {
  const response = await query(
    withNetworkingQuery(networkingPaths.templates, {
      cursor: options.cursor,
      limit: options.limit ?? 100,
    }),
    options.signal,
  );
  return (await response.json()) as NetworkingTemplatePage;
}

export async function createTemplate(
  input: TemplateCreateInput,
  idempotencyKey: string,
): Promise<NetworkingTemplate> {
  const response = await mutate(networkingPaths.templates, {
    body: JSON.stringify(input),
    headers: mutationHeaders(undefined, idempotencyKey),
    method: "POST",
  });
  return (await response.json()) as NetworkingTemplate;
}

export async function updateTemplate(
  template: Pick<NetworkingTemplate, "id" | "version">,
  input: TemplateUpdateInput,
  idempotencyKey: string,
): Promise<NetworkingTemplate> {
  const response = await mutate(networkingPaths.template(template.id), {
    body: JSON.stringify(input),
    headers: mutationHeaders(template.version, idempotencyKey),
    method: "PATCH",
  });
  return (await response.json()) as NetworkingTemplate;
}

export async function listReminders(
  contactId: string,
  options: PageOptions = {},
): Promise<ReminderPage> {
  const response = await query(
    withNetworkingQuery(networkingPaths.reminders(contactId), {
      cursor: options.cursor,
      limit: options.limit ?? 100,
    }),
    options.signal,
  );
  return (await response.json()) as ReminderPage;
}

export async function createReminder(
  contactId: string,
  input: ReminderCreateInput,
  idempotencyKey: string,
): Promise<Reminder> {
  const response = await mutate(networkingPaths.reminders(contactId), {
    body: JSON.stringify(input),
    headers: mutationHeaders(undefined, idempotencyKey),
    method: "POST",
  });
  return (await response.json()) as Reminder;
}

export async function getReminderExecutions(
  reminderIds: readonly string[],
  signal?: AbortSignal,
): Promise<ReminderExecutionBatch> {
  const response = await query(
    withNetworkingQuery(networkingPaths.reminderExecutions, {
      reminderId: reminderIds,
    }),
    signal,
  );
  return (await response.json()) as ReminderExecutionBatch;
}

export async function listDueReminders(
  options: PageOptions = {},
): Promise<DueReminderPage> {
  const response = await query(
    withNetworkingQuery(networkingPaths.dueReminders, {
      cursor: options.cursor,
      limit: options.limit ?? 50,
    }),
    options.signal,
  );
  return (await response.json()) as DueReminderPage;
}

export async function resolveReminder(
  reminder: Pick<Reminder, "id" | "version">,
  input: ReminderResolutionInput,
  idempotencyKey: string,
): Promise<Reminder> {
  const response = await mutate(networkingPaths.reminderActions(reminder.id), {
    body: JSON.stringify(input),
    headers: mutationHeaders(reminder.version, idempotencyKey),
    method: "POST",
  });
  return (await response.json()) as Reminder;
}

export async function updateReminder(
  reminder: Pick<Reminder, "id" | "version">,
  input: ReminderUpdateInput,
  idempotencyKey: string,
): Promise<Reminder> {
  const response = await mutate(networkingPaths.reminder(reminder.id), {
    body: JSON.stringify(input),
    headers: mutationHeaders(reminder.version, idempotencyKey),
    method: "PATCH",
  });
  return (await response.json()) as Reminder;
}

export { ApiRequestError };
