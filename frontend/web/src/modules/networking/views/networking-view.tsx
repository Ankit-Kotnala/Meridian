"use client";

import {
  Building2,
  ChevronRight,
  FileText,
  Plus,
  RefreshCcw,
  Search,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from "react";

import {
  Alert,
  Badge,
  Button,
  CheckboxField,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
  Tabs,
  buttonStyles,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import { contactConsentPolicyVersion } from "../api/consent-policy";
import {
  ApiRequestError,
  createContact,
  createOrganization,
  createTemplate,
  deleteOrganization,
  listDueReminders,
  listContacts,
  listOrganizations,
  listTemplates,
  resolveReminder,
  updateOrganization,
  updateTemplate,
} from "../api/networking-api";
import type {
  Contact,
  ContactCreateInput,
  ContactReferralState,
  DueReminderPage,
  NetworkingTemplate,
  Organization,
  RelationshipStage,
  ReminderResolutionInput,
  TemplateKind,
} from "../api/types";
import { useIntentActivity } from "../hooks/use-intent-activity";

const relationshipStages: readonly RelationshipStage[] = [
  "new",
  "warm",
  "active",
  "trusted",
  "dormant",
  "archived",
];
const contactReferralStates: readonly ContactReferralState[] = [
  "none",
  "considering",
  "requested",
  "referred",
  "declined",
  "cancelled",
];
const templateKinds: readonly TemplateKind[] = [
  "introduction",
  "follow_up",
  "referral_request",
  "thank_you",
  "custom",
];

function humanize(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function dateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function uniqueById<T extends { id: string }>(values: readonly T[]): T[] {
  const seen = new Set<string>();
  return values.filter((value) => {
    if (seen.has(value.id)) return false;
    seen.add(value.id);
    return true;
  });
}

function splitTags(value: FormDataEntryValue | null): string[] {
  return String(value ?? "")
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function contactTone(stage: RelationshipStage) {
  if (stage === "trusted" || stage === "active") return "success" as const;
  if (stage === "dormant" || stage === "archived") return "neutral" as const;
  return "primary" as const;
}

type Filters = {
  contactQuery: string;
  organizationId: string;
  organizationQuery: string;
  organizationTag: string;
  outreachConsent: "" | "true" | "false";
  referralState: ContactReferralState | "";
  relationshipStage: RelationshipStage | "";
  tag: string;
};

const initialFilters: Filters = {
  contactQuery: "",
  organizationId: "",
  organizationQuery: "",
  organizationTag: "",
  outreachConsent: "",
  referralState: "",
  relationshipStage: "",
  tag: "",
};

type NetworkingState =
  | { status: "loading" }
  | {
      contacts: Contact[];
      contactCursor: string | null;
      dueCursor: string | null;
      dueLoaded: boolean;
      dueReminders: DueReminderPage["data"];
      organizations: Organization[];
      organizationCursor: string | null;
      status: "ready";
      templateCursor: string | null;
      templates: NetworkingTemplate[];
    }
  | { message: string; status: "error" };

export function NetworkingView() {
  const [state, setState] = useState<NetworkingState>({ status: "loading" });
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const [draftFilters, setDraftFilters] = useState<Filters>(initialFilters);
  const [templateQuery, setTemplateQuery] = useState("");
  const [templateKind, setTemplateKind] = useState<TemplateKind | "">("");
  const [activeTab, setActiveTab] = useState("contacts");
  const [showContactForm, setShowContactForm] = useState(false);
  const [showOrganizationForm, setShowOrganizationForm] = useState(false);
  const [showTemplateForm, setShowTemplateForm] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Organization>();
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const {
    begin: beginActivity,
    finish: finishActivity,
    isBusy,
  } = useIntentActivity();
  const requestEpoch = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const intentKeys = useRef(new Map<string, string>());

  const stableIntent = useCallback((intent: string) => {
    const existing = intentKeys.current.get(intent);
    if (existing) return existing;
    const key = `networking-web:${crypto.randomUUID()}`;
    intentKeys.current.set(intent, key);
    return key;
  }, []);

  const clearIntent = useCallback((intent: string) => {
    intentKeys.current.delete(intent);
  }, []);

  const load = useCallback(
    async (authoritativeMessage?: string) => {
      controller.current?.abort();
      const nextController = new AbortController();
      controller.current = nextController;
      const epoch = ++requestEpoch.current;
      setFailure(undefined);
      setState({ status: "loading" });
      try {
        const [contacts, organizations, templates] = await Promise.all([
          listContacts({
            limit: 50,
            ...(filters.organizationId
              ? { organizationId: filters.organizationId }
              : {}),
            ...(filters.outreachConsent === ""
              ? {}
              : { outreachConsent: filters.outreachConsent === "true" }),
            q: filters.contactQuery,
            referralState: filters.referralState,
            relationshipStage: filters.relationshipStage,
            signal: nextController.signal,
            tag: filters.tag,
          }),
          listOrganizations({
            limit: 50,
            q: filters.organizationQuery,
            signal: nextController.signal,
            tag: filters.organizationTag,
          }),
          listTemplates({ limit: 100, signal: nextController.signal }),
        ]);
        if (epoch !== requestEpoch.current || nextController.signal.aborted)
          return;
        setState({
          contacts: contacts.data,
          contactCursor: contacts.page.nextCursor,
          dueCursor: null,
          dueLoaded: false,
          dueReminders: [],
          organizations: organizations.data,
          organizationCursor: organizations.page.nextCursor,
          status: "ready",
          templateCursor: templates.page.nextCursor,
          templates: templates.data,
        });
        if (authoritativeMessage) setFailure(authoritativeMessage);
      } catch (error) {
        if (epoch !== requestEpoch.current || nextController.signal.aborted)
          return;
        setState({
          message: requestErrorMessage(
            error,
            "The Networking workspace could not be loaded.",
          ),
          status: "error",
        });
      }
    },
    [filters],
  );

  useEffect(() => {
    queueMicrotask(() => void load());
    return () => {
      controller.current?.abort();
      requestEpoch.current += 1;
    };
  }, [load]);

  useEffect(() => {
    if (activeTab !== "due" || state.status !== "ready" || state.dueLoaded) {
      return;
    }
    const epoch = requestEpoch.current;
    queueMicrotask(async () => {
      try {
        const page = await listDueReminders({ limit: 50 });
        if (epoch !== requestEpoch.current) return;
        setState((current) =>
          current.status === "ready"
            ? {
                ...current,
                dueCursor: page.page.nextCursor,
                dueLoaded: true,
                dueReminders: page.data,
              }
            : current,
        );
      } catch (error) {
        if (epoch !== requestEpoch.current) return;
        setFailure(
          requestErrorMessage(
            error,
            "Actionable local reminders could not be loaded.",
          ),
        );
      }
    });
  }, [activeTab, state]);

  const visibleTemplates = useMemo(() => {
    if (state.status !== "ready") return [];
    const query = templateQuery.trim().toLocaleLowerCase();
    return state.templates.filter(
      (template) =>
        (!templateKind || template.kind === templateKind) &&
        (!query ||
          `${template.name} ${template.body}`
            .toLocaleLowerCase()
            .includes(query)),
    );
  }, [state, templateKind, templateQuery]);

  function applyContactFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFilters((current) => ({
      ...current,
      contactQuery: draftFilters.contactQuery,
      organizationId: draftFilters.organizationId,
      outreachConsent: draftFilters.outreachConsent,
      referralState: draftFilters.referralState,
      relationshipStage: draftFilters.relationshipStage,
      tag: draftFilters.tag,
    }));
  }

  function applyOrganizationFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFilters((current) => ({
      ...current,
      organizationQuery: draftFilters.organizationQuery,
      organizationTag: draftFilters.organizationTag,
    }));
  }

  async function loadMore(
    collection: "contacts" | "organizations" | "templates",
  ) {
    if (state.status !== "ready") return;
    const cursor =
      collection === "contacts"
        ? state.contactCursor
        : collection === "organizations"
          ? state.organizationCursor
          : state.templateCursor;
    if (!cursor) return;
    const activityKey = `more-${collection}`;
    const activityEpoch = beginActivity(activityKey);
    if (activityEpoch === null) return;
    const epoch = requestEpoch.current;
    setFailure(undefined);
    try {
      if (collection === "contacts") {
        const page = await listContacts({
          cursor,
          limit: 50,
          ...(filters.organizationId
            ? { organizationId: filters.organizationId }
            : {}),
          ...(filters.outreachConsent === ""
            ? {}
            : { outreachConsent: filters.outreachConsent === "true" }),
          q: filters.contactQuery,
          referralState: filters.referralState,
          relationshipStage: filters.relationshipStage,
          tag: filters.tag,
        });
        if (epoch !== requestEpoch.current) return;
        setState((current) =>
          current.status === "ready" && current.contactCursor === cursor
            ? {
                ...current,
                contacts: uniqueById([...current.contacts, ...page.data]),
                contactCursor: page.page.nextCursor,
              }
            : current,
        );
      } else if (collection === "organizations") {
        const page = await listOrganizations({
          cursor,
          limit: 50,
          q: filters.organizationQuery,
          tag: filters.organizationTag,
        });
        if (epoch !== requestEpoch.current) return;
        setState((current) =>
          current.status === "ready" && current.organizationCursor === cursor
            ? {
                ...current,
                organizationCursor: page.page.nextCursor,
                organizations: uniqueById([
                  ...current.organizations,
                  ...page.data,
                ]),
              }
            : current,
        );
      } else {
        const page = await listTemplates({ cursor, limit: 100 });
        if (epoch !== requestEpoch.current) return;
        setState((current) =>
          current.status === "ready" && current.templateCursor === cursor
            ? {
                ...current,
                templateCursor: page.page.nextCursor,
                templates: uniqueById([...current.templates, ...page.data]),
              }
            : current,
        );
      }
    } catch (error) {
      if (epoch !== requestEpoch.current) return;
      setFailure(
        requestErrorMessage(error, `More ${collection} could not be loaded.`),
      );
    } finally {
      finishActivity(activityKey, activityEpoch);
    }
  }

  async function loadMoreDueReminders() {
    if (state.status !== "ready" || !state.dueCursor) return;
    const cursor = state.dueCursor;
    const activityKey = "more-due-reminders";
    const activityEpoch = beginActivity(activityKey);
    if (activityEpoch === null) return;
    const epoch = requestEpoch.current;
    try {
      const page = await listDueReminders({ cursor, limit: 50 });
      if (epoch !== requestEpoch.current) return;
      setState((current) =>
        current.status === "ready" && current.dueCursor === cursor
          ? {
              ...current,
              dueCursor: page.page.nextCursor,
              dueReminders: [
                ...current.dueReminders,
                ...page.data.filter(
                  (candidate) =>
                    !current.dueReminders.some(
                      (item) =>
                        item.execution.occurrenceId ===
                        candidate.execution.occurrenceId,
                    ),
                ),
              ],
            }
          : current,
      );
    } catch (error) {
      if (epoch === requestEpoch.current) {
        setFailure(
          requestErrorMessage(error, "More due reminders could not be loaded."),
        );
      }
    } finally {
      finishActivity(activityKey, activityEpoch);
    }
  }

  async function actOnDueReminder(
    item: DueReminderPage["data"][number],
    input: ReminderResolutionInput,
  ) {
    const activityKey = `due-reminder-${item.reminder.id}`;
    const activityEpoch = beginActivity(activityKey);
    if (activityEpoch === null) return;
    const intent = `due-reminder:${item.reminder.id}:${item.reminder.version}:${JSON.stringify(input)}`;
    setFailure(undefined);
    setSuccess(undefined);
    try {
      await resolveReminder(item.reminder, input, stableIntent(intent));
      clearIntent(intent);
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              dueReminders: current.dueReminders.filter(
                (candidate) =>
                  candidate.execution.occurrenceId !==
                  item.execution.occurrenceId,
              ),
            }
          : current,
      );
      setSuccess(
        input.action === "snooze"
          ? "Reminder snoozed locally."
          : input.action === "complete"
            ? "Reminder completed by you."
            : "Reminder acknowledged by you.",
      );
    } catch (error) {
      const stale =
        error instanceof ApiRequestError &&
        (error.failure.status === 409 || error.failure.status === 412);
      if (stale) {
        setState((current) =>
          current.status === "ready"
            ? { ...current, dueLoaded: false, dueReminders: [] }
            : current,
        );
        setFailure(
          "The reminder changed elsewhere. The authoritative due queue is reloading.",
        );
      } else {
        setFailure(
          requestErrorMessage(error, "The reminder action could not be saved."),
        );
      }
    } finally {
      finishActivity(activityKey, activityEpoch);
    }
  }

  async function submitContact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    if (
      form.get("collectionAttested") !== "on" ||
      form.get("storageAttested") !== "on"
    ) {
      setFailure(
        "Collection and storage consent attestations must both be explicitly accepted.",
      );
      return;
    }
    const input: ContactCreateInput = {
      consent: {
        collectionAttested: true,
        outreachAttested: form.get("outreachAttested") === "on",
        policyVersion: contactConsentPolicyVersion,
        storageAttested: true,
      },
      email: String(form.get("email") ?? "").trim() || null,
      location: String(form.get("location") ?? "").trim() || null,
      name: String(form.get("name") ?? "").trim(),
      organizationId: String(form.get("organizationId") ?? "") || null,
      phone: String(form.get("phone") ?? "").trim() || null,
      profileUrl: String(form.get("profileUrl") ?? "").trim() || null,
      referralState: String(form.get("referralState")) as ContactReferralState,
      relationshipStage: String(
        form.get("relationshipStage"),
      ) as RelationshipStage,
      role: String(form.get("role") ?? "").trim() || null,
      tags: splitTags(form.get("tags")),
    };
    const intent = `contact:${JSON.stringify(input)}`;
    const activityEpoch = beginActivity("contact");
    if (activityEpoch === null) return;
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const contact = await createContact(input, stableIntent(intent));
      clearIntent(intent);
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              contacts: uniqueById([contact, ...current.contacts]),
            }
          : current,
      );
      setSuccess(
        `${contact.name} saved with separate collection, storage, and outreach consent state.`,
      );
      setShowContactForm(false);
      formElement.reset();
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "The private contact could not be saved."),
      );
    } finally {
      finishActivity("contact", activityEpoch);
    }
  }

  async function submitOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const input = {
      industry: String(form.get("industry") ?? "").trim() || null,
      location: String(form.get("location") ?? "").trim() || null,
      name: String(form.get("name") ?? "").trim(),
      tags: splitTags(form.get("tags")),
      website: String(form.get("website") ?? "").trim() || null,
    };
    const intent = `organization:${JSON.stringify(input)}`;
    const activityEpoch = beginActivity("organization");
    if (activityEpoch === null) return;
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const organization = await createOrganization(
        input,
        stableIntent(intent),
      );
      clearIntent(intent);
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              organizations: uniqueById([
                organization,
                ...current.organizations,
              ]),
            }
          : current,
      );
      setSuccess(`${organization.name} saved.`);
      setShowOrganizationForm(false);
      formElement.reset();
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "The organization could not be saved."),
      );
    } finally {
      finishActivity("organization", activityEpoch);
    }
  }

  async function saveOrganization(
    organization: Organization,
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const input = {
      industry: String(form.get("industry") ?? "").trim() || null,
      location: String(form.get("location") ?? "").trim() || null,
      name: String(form.get("name") ?? "").trim(),
      tags: splitTags(form.get("tags")),
      website: String(form.get("website") ?? "").trim() || null,
    };
    const intent = `organization-update:${organization.id}:${organization.version}:${JSON.stringify(input)}`;
    const activityKey = `organization-${organization.id}`;
    const activityEpoch = beginActivity(activityKey);
    if (activityEpoch === null) return;
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const updated = await updateOrganization(
        organization,
        input,
        stableIntent(intent),
      );
      clearIntent(intent);
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              organizations: current.organizations.map((item) =>
                item.id === updated.id ? updated : item,
              ),
            }
          : current,
      );
      setSuccess(`${updated.name} updated.`);
    } catch (error) {
      await conflictOrFailure(
        error,
        "The organization could not be updated.",
        "The organization changed in another session. Authoritative Networking data was reloaded.",
      );
    } finally {
      finishActivity(activityKey, activityEpoch);
    }
  }

  async function removeOrganization() {
    const organization = deleteTarget;
    if (!organization) return;
    const intent = `organization-delete:${organization.id}:${organization.version}`;
    const activityKey = `organization-${organization.id}`;
    const activityEpoch = beginActivity(activityKey);
    if (activityEpoch === null) return;
    setFailure(undefined);
    try {
      await deleteOrganization(organization, stableIntent(intent));
      clearIntent(intent);
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              organizations: current.organizations.filter(
                (item) => item.id !== organization.id,
              ),
            }
          : current,
      );
      setDeleteTarget(undefined);
      setSuccess(
        `${organization.name} deleted. Linked contacts remain private and are detached.`,
      );
    } catch (error) {
      setDeleteTarget(undefined);
      await conflictOrFailure(
        error,
        "The organization could not be deleted.",
        "The organization changed in another session. Authoritative Networking data was reloaded.",
      );
    } finally {
      finishActivity(activityKey, activityEpoch);
    }
  }

  async function submitTemplate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    if (form.get("userReviewed") !== "on") {
      setFailure("Confirm that you reviewed the template before saving it.");
      return;
    }
    const input = {
      body: String(form.get("body") ?? "").trim(),
      kind: String(form.get("kind")) as TemplateKind,
      name: String(form.get("name") ?? "").trim(),
      userReviewed: true as const,
    };
    const intent = `template:${JSON.stringify(input)}`;
    const activityEpoch = beginActivity("template");
    if (activityEpoch === null) return;
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const template = await createTemplate(input, stableIntent(intent));
      clearIntent(intent);
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              templates: uniqueById([template, ...current.templates]),
            }
          : current,
      );
      setSuccess(`${template.name} saved for manual review and use.`);
      setShowTemplateForm(false);
      formElement.reset();
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "The reviewed template could not be saved."),
      );
    } finally {
      finishActivity("template", activityEpoch);
    }
  }

  async function saveTemplate(
    template: NetworkingTemplate,
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (form.get("userReviewed") !== "on") {
      setFailure("Confirm that you reviewed the edited template.");
      return;
    }
    const input = {
      body: String(form.get("body") ?? "").trim(),
      kind: String(form.get("kind")) as TemplateKind,
      name: String(form.get("name") ?? "").trim(),
      userReviewed: true as const,
    };
    const intent = `template-update:${template.id}:${template.version}:${JSON.stringify(input)}`;
    const activityKey = `template-${template.id}`;
    const activityEpoch = beginActivity(activityKey);
    if (activityEpoch === null) return;
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const updated = await updateTemplate(
        template,
        input,
        stableIntent(intent),
      );
      clearIntent(intent);
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              templates: current.templates.map((item) =>
                item.id === updated.id ? updated : item,
              ),
            }
          : current,
      );
      setSuccess(`${updated.name} updated after explicit review.`);
    } catch (error) {
      await conflictOrFailure(
        error,
        "The template could not be updated.",
        "The template changed in another session. Authoritative Networking data was reloaded.",
      );
    } finally {
      finishActivity(activityKey, activityEpoch);
    }
  }

  async function conflictOrFailure(
    error: unknown,
    fallback: string,
    conflict: string,
  ) {
    const stale =
      error instanceof ApiRequestError &&
      (error.failure.status === 409 || error.failure.status === 412);
    if (stale) await load(conflict);
    else setFailure(requestErrorMessage(error, fallback));
  }

  if (state.status === "error") {
    return (
      <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={state.message}
          onRetry={() => void load()}
          title="Networking unavailable"
        />
      </main>
    );
  }

  if (state.status === "loading") {
    return (
      <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
        <LoadingSkeleton variant="page" />
      </main>
    );
  }

  return (
    <main
      className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8"
      id="main-content"
    >
      <PageHeader
        actions={
          <Button onClick={() => void load()} variant="secondary">
            <RefreshCcw aria-hidden="true" className="size-4" />
            Refresh
          </Button>
        }
        description="Maintain contacts, relationship history, referrals, reviewed templates, and local reminders. Meridian never scrapes contacts, imports them without consent, or sends outreach."
        eyebrow="Relationships"
        title="A private, consent-based relationship workspace"
      />

      <Alert title="No external delivery or scraping" tone="warning">
        Interactions record what already happened. Templates are reviewable
        local text, and reminders are workspace state only. There are no import,
        scrape, email, message, or social-network send controls.
      </Alert>

      {failure && (
        <Alert title="Review current data" tone="danger">
          <p>{failure}</p>
          <Button
            className="mt-3 min-h-9 px-3"
            onClick={() => void load()}
            variant="secondary"
          >
            Reload authoritative data
          </Button>
        </Alert>
      )}
      {success && (
        <Alert title="Networking updated" tone="success">
          {success}
        </Alert>
      )}

      <Tabs
        label="Networking workspace"
        onValueChange={setActiveTab}
        tabs={[
          {
            id: "contacts",
            label: `Contacts (${state.contacts.length})`,
            panel: (
              <ContactsPanel
                busy={isBusy}
                contactCursor={state.contactCursor}
                contacts={state.contacts}
                draftFilters={draftFilters}
                onApply={applyContactFilters}
                onDraftFilters={setDraftFilters}
                onLoadMore={() => void loadMore("contacts")}
                onOpenForm={() => setShowContactForm((open) => !open)}
                onSubmit={submitContact}
                organizations={state.organizations}
                showForm={showContactForm}
              />
            ),
          },
          {
            id: "due",
            label: `Due reminders (${state.dueReminders.length})`,
            panel: (
              <DueRemindersPanel
                busy={isBusy}
                cursor={state.dueCursor}
                items={state.dueReminders}
                loaded={state.dueLoaded}
                onAction={(item, input) => void actOnDueReminder(item, input)}
                onLoadMore={() => void loadMoreDueReminders()}
              />
            ),
          },
          {
            id: "organizations",
            label: `Organizations (${state.organizations.length})`,
            panel: (
              <OrganizationsPanel
                busy={isBusy}
                draftFilters={draftFilters}
                onApply={applyOrganizationFilters}
                onDelete={setDeleteTarget}
                onDraftFilters={setDraftFilters}
                onLoadMore={() => void loadMore("organizations")}
                onOpenForm={() => setShowOrganizationForm((open) => !open)}
                onSave={(organization, event) =>
                  void saveOrganization(organization, event)
                }
                onSubmit={submitOrganization}
                organizationCursor={state.organizationCursor}
                organizations={state.organizations}
                showForm={showOrganizationForm}
              />
            ),
          },
          {
            id: "templates",
            label: `Reviewed templates (${state.templates.length})`,
            panel: (
              <TemplatesPanel
                busy={isBusy}
                onKind={setTemplateKind}
                onLoadMore={() => void loadMore("templates")}
                onOpenForm={() => setShowTemplateForm((open) => !open)}
                onQuery={setTemplateQuery}
                onSave={(template, event) => void saveTemplate(template, event)}
                onSubmit={submitTemplate}
                query={templateQuery}
                selectedKind={templateKind}
                showForm={showTemplateForm}
                templateCursor={state.templateCursor}
                templates={visibleTemplates}
              />
            ),
          },
        ]}
        value={activeTab}
      />

      <ConfirmDialog
        confirmLabel="Delete organization"
        description="The organization is removed. Active linked contacts remain private records and are detached from it."
        loading={
          Boolean(deleteTarget) && isBusy(`organization-${deleteTarget?.id}`)
        }
        onConfirm={() => void removeOrganization()}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(undefined);
        }}
        open={Boolean(deleteTarget)}
        title={`Delete ${deleteTarget?.name ?? "this organization"}?`}
      />
    </main>
  );
}

function DueRemindersPanel({
  busy,
  cursor,
  items,
  loaded,
  onAction,
  onLoadMore,
}: {
  busy: (key: string) => boolean;
  cursor: string | null;
  items: DueReminderPage["data"];
  loaded: boolean;
  onAction: (
    item: DueReminderPage["data"][number],
    input: ReminderResolutionInput,
  ) => void;
  onLoadMore: () => void;
}) {
  if (!loaded) {
    return (
      <div className="pt-5">
        <LoadingSkeleton />
      </div>
    );
  }
  return (
    <div className="space-y-4 pt-5">
      <Alert title="Local and owner-actionable" tone="warning">
        The worker only places due reminders in this private queue. Nothing is
        sent externally, and a reminder stays here until you act on it.
      </Alert>
      {items.length === 0 ? (
        <EmptyState
          description="There are no local reminders waiting for your action."
          title="No due reminders"
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {items.map((item) => (
            <DueReminderCard
              busy={busy(`due-reminder-${item.reminder.id}`)}
              item={item}
              key={item.execution.occurrenceId}
              onAction={(input) => onAction(item, input)}
            />
          ))}
        </div>
      )}
      {cursor && (
        <Button
          disabled={busy("more-due-reminders")}
          onClick={onLoadMore}
          variant="secondary"
        >
          Load more due reminders
        </Button>
      )}
    </div>
  );
}

function DueReminderCard({
  busy,
  item,
  onAction,
}: {
  busy: boolean;
  item: DueReminderPage["data"][number];
  onAction: (input: ReminderResolutionInput) => void;
}) {
  const [snoozeUntil, setSnoozeUntil] = useState("");
  return (
    <article className="rounded-xl border border-line bg-surface p-4 shadow-sm">
      <Badge tone="warning">Due</Badge>
      <h2 className="mt-2 font-black text-foreground">{item.reminder.title}</h2>
      <p className="mt-1 text-xs text-muted">
        Scheduled {dateTime(item.execution.scheduledFor)} · Local occurrence{" "}
        {item.execution.occurrenceNumber}
      </p>
      <Link
        className="mt-3 inline-flex min-h-9 items-center font-bold text-primary underline"
        href={`/networking/contacts/${item.reminder.contactId}`}
      >
        Open private contact
      </Link>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          disabled={busy}
          onClick={() => onAction({ action: "acknowledge" })}
          type="button"
          variant="secondary"
        >
          Acknowledge
        </Button>
        <Button
          disabled={busy}
          onClick={() => onAction({ action: "complete" })}
          type="button"
        >
          Complete
        </Button>
      </div>
      <div className="mt-3 space-y-2">
        <LabeledInput
          id={`due-${item.reminder.id}-snooze`}
          label="Snooze until"
          onChange={(event) => setSnoozeUntil(event.target.value)}
          type="datetime-local"
        />
        <Button
          disabled={busy || !snoozeUntil}
          onClick={() => {
            if (!snoozeUntil) return;
            onAction({
              action: "snooze",
              snoozeUntil: new Date(snoozeUntil).toISOString(),
            });
          }}
          type="button"
          variant="secondary"
        >
          Snooze
        </Button>
      </div>
    </article>
  );
}

function ContactsPanel({
  busy,
  contactCursor,
  contacts,
  draftFilters,
  onApply,
  onDraftFilters,
  onLoadMore,
  onOpenForm,
  onSubmit,
  organizations,
  showForm,
}: {
  busy: (key: string) => boolean;
  contactCursor: string | null;
  contacts: Contact[];
  draftFilters: Filters;
  onApply: (event: FormEvent<HTMLFormElement>) => void;
  onDraftFilters: (filters: Filters) => void;
  onLoadMore: () => void;
  onOpenForm: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  organizations: Organization[];
  showForm: boolean;
}) {
  return (
    <div className="space-y-5 pt-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <form
          className="grid flex-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
          onSubmit={onApply}
        >
          <NetworkInput
            aria-label="Search contacts"
            onChange={(event) =>
              onDraftFilters({
                ...draftFilters,
                contactQuery: event.target.value,
              })
            }
            placeholder="Search contacts"
            value={draftFilters.contactQuery}
          />
          <Select
            aria-label="Relationship stage"
            onChange={(event) =>
              onDraftFilters({
                ...draftFilters,
                relationshipStage: event.target.value as RelationshipStage | "",
              })
            }
            value={draftFilters.relationshipStage}
          >
            <option value="">All relationship stages</option>
            {relationshipStages.map((stage) => (
              <option key={stage} value={stage}>
                {humanize(stage)}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Outreach consent"
            onChange={(event) =>
              onDraftFilters({
                ...draftFilters,
                outreachConsent: event.target.value as "" | "true" | "false",
              })
            }
            value={draftFilters.outreachConsent}
          >
            <option value="">Any outreach consent</option>
            <option value="true">Outreach allowed</option>
            <option value="false">Outreach not allowed</option>
          </Select>
          <Button type="submit" variant="secondary">
            <Search aria-hidden="true" className="size-4" />
            Apply filters
          </Button>
          <Select
            aria-label="Organization filter"
            onChange={(event) =>
              onDraftFilters({
                ...draftFilters,
                organizationId: event.target.value,
              })
            }
            value={draftFilters.organizationId}
          >
            <option value="">All organizations</option>
            {organizations.map((organization) => (
              <option key={organization.id} value={organization.id}>
                {organization.name}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Referral state"
            onChange={(event) =>
              onDraftFilters({
                ...draftFilters,
                referralState: event.target.value as ContactReferralState | "",
              })
            }
            value={draftFilters.referralState}
          >
            <option value="">Any referral state</option>
            {contactReferralStates.map((status) => (
              <option key={status} value={status}>
                {humanize(status)}
              </option>
            ))}
          </Select>
          <NetworkInput
            aria-label="Contact tag filter"
            onChange={(event) =>
              onDraftFilters({ ...draftFilters, tag: event.target.value })
            }
            placeholder="Filter by exact tag"
            value={draftFilters.tag}
          />
        </form>
        <Button onClick={onOpenForm}>
          <Plus aria-hidden="true" className="size-4" />
          {showForm ? "Close contact form" : "Add contact"}
        </Button>
      </div>

      {showForm && (
        <ContactCreateForm
          busy={busy("contact")}
          onSubmit={onSubmit}
          organizations={organizations}
        />
      )}

      {contacts.length === 0 ? (
        <EmptyState
          action={<Button onClick={onOpenForm}>Add a consented contact</Button>}
          description="Contacts appear only after you explicitly attest collection and storage consent."
          title="No private contacts"
        />
      ) : (
        <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {contacts.map((contact) => (
            <li
              className="rounded-xl border border-line bg-surface p-4 shadow-sm"
              key={contact.id}
            >
              <div className="flex flex-wrap gap-2">
                <Badge tone={contactTone(contact.relationshipStage)}>
                  {humanize(contact.relationshipStage)}
                </Badge>
                <Badge
                  tone={contact.consent.allowsOutreach ? "success" : "warning"}
                >
                  Outreach{" "}
                  {contact.consent.allowsOutreach ? "allowed" : "blocked"}
                </Badge>
              </div>
              <h2 className="mt-3 font-black text-foreground">
                {contact.name}
              </h2>
              <p className="mt-1 text-sm text-muted">
                {[contact.role, contact.location].filter(Boolean).join(" · ") ||
                  "Role and location not recorded"}
              </p>
              {contact.tags.length > 0 && (
                <p className="mt-3 text-xs text-muted">
                  Tags: {contact.tags.join(", ")}
                </p>
              )}
              <Link
                className={`${buttonStyles.base} ${buttonStyles.ghost} mt-3 -ml-3`}
                href={`/networking/contacts/${contact.id}`}
              >
                Open private record
                <ChevronRight aria-hidden="true" className="size-4" />
              </Link>
            </li>
          ))}
        </ul>
      )}
      {contactCursor && (
        <Button
          disabled={busy("more-contacts")}
          onClick={onLoadMore}
          variant="secondary"
        >
          Load more contacts
        </Button>
      )}
    </div>
  );
}

function ContactCreateForm({
  busy,
  onSubmit,
  organizations,
}: {
  busy: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  organizations: Organization[];
}) {
  return (
    <form
      className="space-y-5 rounded-xl border border-line bg-surface p-4 shadow-sm sm:p-5"
      onSubmit={onSubmit}
    >
      <div>
        <h2 className="font-black text-foreground">Add a private contact</h2>
        <p className="mt-1 text-sm text-muted">
          Enter only data you are permitted to collect and store. Meridian does
          not fetch the profile URL or import contact data.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <LabeledInput id="contact-name" label="Name" name="name" required />
        <LabeledInput id="contact-role" label="Role" name="role" />
        <label className="space-y-2 text-sm font-bold text-foreground">
          Organization
          <Select name="organizationId">
            <option value="">No organization</option>
            {organizations.map((organization) => (
              <option key={organization.id} value={organization.id}>
                {organization.name}
              </option>
            ))}
          </Select>
        </label>
        <LabeledInput
          id="contact-email"
          label="Email"
          name="email"
          type="email"
        />
        <LabeledInput id="contact-phone" label="Phone" name="phone" />
        <LabeledInput
          id="contact-profile-url"
          label="Profile URL (stored only)"
          name="profileUrl"
          type="url"
        />
        <LabeledInput id="contact-location" label="Location" name="location" />
        <label className="space-y-2 text-sm font-bold text-foreground">
          Relationship stage
          <Select defaultValue="new" name="relationshipStage">
            {relationshipStages.map((stage) => (
              <option key={stage} value={stage}>
                {humanize(stage)}
              </option>
            ))}
          </Select>
        </label>
        <label className="space-y-2 text-sm font-bold text-foreground">
          Referral state
          <Select defaultValue="none" name="referralState">
            {contactReferralStates.map((state) => (
              <option key={state} value={state}>
                {humanize(state)}
              </option>
            ))}
          </Select>
        </label>
        <LabeledInput
          id="contact-tags"
          label="Tags (comma separated)"
          name="tags"
        />
        <p className="text-sm text-muted">
          Consent policy version:{" "}
          <span className="font-semibold text-foreground">
            {contactConsentPolicyVersion}
          </span>
        </p>
      </div>
      <fieldset className="space-y-3 rounded-xl border border-line p-4">
        <legend className="px-1 text-sm font-black text-foreground">
          Purpose-scoped consent attestation
        </legend>
        <CheckboxField
          description="Required. You attest that this contact's information may be collected for this private workspace."
          id="contact-consent-collection"
          label="Collection consent is attested"
          name="collectionAttested"
          required
        />
        <CheckboxField
          description="Required. You attest that this contact's information may be stored in Meridian."
          id="contact-consent-storage"
          label="Storage consent is attested"
          name="storageAttested"
          required
        />
        <CheckboxField
          description="Optional. Without this, new outreach-related interactions, referrals, and reminders remain blocked."
          id="contact-consent-outreach"
          label="Outreach consent is attested"
          name="outreachAttested"
        />
      </fieldset>
      <Button disabled={busy} type="submit">
        {busy ? "Saving…" : "Save consented contact"}
      </Button>
    </form>
  );
}

function OrganizationsPanel({
  busy,
  draftFilters,
  onApply,
  onDelete,
  onDraftFilters,
  onLoadMore,
  onOpenForm,
  onSave,
  onSubmit,
  organizationCursor,
  organizations,
  showForm,
}: {
  busy: (key: string) => boolean;
  draftFilters: Filters;
  onApply: (event: FormEvent<HTMLFormElement>) => void;
  onDelete: (organization: Organization) => void;
  onDraftFilters: (filters: Filters) => void;
  onLoadMore: () => void;
  onOpenForm: () => void;
  onSave: (
    organization: Organization,
    event: FormEvent<HTMLFormElement>,
  ) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  organizationCursor: string | null;
  organizations: Organization[];
  showForm: boolean;
}) {
  return (
    <div className="space-y-5 pt-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <form className="flex flex-1 flex-wrap gap-3" onSubmit={onApply}>
          <NetworkInput
            aria-label="Search organizations"
            className="min-w-52 flex-1"
            onChange={(event) =>
              onDraftFilters({
                ...draftFilters,
                organizationQuery: event.target.value,
              })
            }
            placeholder="Search organizations"
            value={draftFilters.organizationQuery}
          />
          <NetworkInput
            aria-label="Organization tag filter"
            className="min-w-48 flex-1"
            onChange={(event) =>
              onDraftFilters({
                ...draftFilters,
                organizationTag: event.target.value,
              })
            }
            placeholder="Filter by exact tag"
            value={draftFilters.organizationTag}
          />
          <Button type="submit" variant="secondary">
            <Search aria-hidden="true" className="size-4" />
            Apply filters
          </Button>
        </form>
        <Button onClick={onOpenForm}>
          <Building2 aria-hidden="true" className="size-4" />
          {showForm ? "Close form" : "Add organization"}
        </Button>
      </div>
      {showForm && (
        <OrganizationCreateForm
          busy={busy("organization")}
          onSubmit={onSubmit}
        />
      )}
      {organizations.length === 0 ? (
        <EmptyState
          description="Create an organization to group private contacts. No external lookup is performed."
          title="No organizations"
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {organizations.map((organization) => (
            <OrganizationForm
              busy={busy(`organization-${organization.id}`)}
              key={`${organization.id}-${organization.version}`}
              onDelete={() => onDelete(organization)}
              onSubmit={(event) => onSave(organization, event)}
              organization={organization}
            />
          ))}
        </div>
      )}
      {organizationCursor && (
        <Button
          disabled={busy("more-organizations")}
          onClick={onLoadMore}
          variant="secondary"
        >
          Load more organizations
        </Button>
      )}
    </div>
  );
}

function OrganizationCreateForm({
  busy,
  onSubmit,
}: {
  busy: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <form
      className="grid gap-4 rounded-xl border border-line bg-surface p-4 sm:grid-cols-2 sm:p-5"
      onSubmit={onSubmit}
    >
      <LabeledInput id="organization-name" label="Name" name="name" required />
      <LabeledInput
        id="organization-website"
        label="Website (stored only)"
        name="website"
        type="url"
      />
      <LabeledInput
        id="organization-industry"
        label="Industry"
        name="industry"
      />
      <LabeledInput
        id="organization-location"
        label="Location"
        name="location"
      />
      <LabeledInput
        id="organization-tags"
        label="Tags (comma separated)"
        name="tags"
      />
      <div className="flex items-end">
        <Button disabled={busy} type="submit">
          {busy ? "Saving…" : "Save organization"}
        </Button>
      </div>
    </form>
  );
}

function OrganizationForm({
  busy,
  onDelete,
  onSubmit,
  organization,
}: {
  busy: boolean;
  onDelete: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  organization: Organization;
}) {
  return (
    <form
      className="grid gap-3 rounded-xl border border-line bg-surface p-4 shadow-sm sm:grid-cols-2"
      onSubmit={onSubmit}
    >
      <LabeledInput
        defaultValue={organization.name}
        id={`organization-${organization.id}-name`}
        label="Name"
        name="name"
        required
      />
      <LabeledInput
        defaultValue={organization.website ?? ""}
        id={`organization-${organization.id}-website`}
        label="Website (stored only)"
        name="website"
        type="url"
      />
      <LabeledInput
        defaultValue={organization.industry ?? ""}
        id={`organization-${organization.id}-industry`}
        label="Industry"
        name="industry"
      />
      <LabeledInput
        defaultValue={organization.location ?? ""}
        id={`organization-${organization.id}-location`}
        label="Location"
        name="location"
      />
      <LabeledInput
        defaultValue={organization.tags.join(", ")}
        id={`organization-${organization.id}-tags`}
        label="Tags"
        name="tags"
      />
      <div className="flex items-end gap-2">
        <Button disabled={busy} type="submit">
          Save
        </Button>
        <Button
          disabled={busy}
          onClick={onDelete}
          type="button"
          variant="danger"
        >
          <Trash2 aria-hidden="true" className="size-4" />
          Delete
        </Button>
      </div>
    </form>
  );
}

function TemplatesPanel({
  busy,
  onKind,
  onLoadMore,
  onOpenForm,
  onQuery,
  onSave,
  onSubmit,
  query,
  selectedKind,
  showForm,
  templateCursor,
  templates,
}: {
  busy: (key: string) => boolean;
  onKind: (kind: TemplateKind | "") => void;
  onLoadMore: () => void;
  onOpenForm: () => void;
  onQuery: (query: string) => void;
  onSave: (
    template: NetworkingTemplate,
    event: FormEvent<HTMLFormElement>,
  ) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  query: string;
  selectedKind: TemplateKind | "";
  showForm: boolean;
  templateCursor: string | null;
  templates: NetworkingTemplate[];
}) {
  return (
    <div className="space-y-5 pt-5">
      <Alert title="Reviewed local text only" tone="info">
        Templates are never sent from Meridian. Review content before saving,
        then copy it manually only where current outreach consent permits.
      </Alert>
      <div className="flex flex-wrap gap-3">
        <NetworkInput
          aria-label="Search reviewed templates"
          className="min-w-56 flex-1"
          onChange={(event) => onQuery(event.target.value)}
          placeholder="Search loaded templates"
          value={query}
        />
        <Select
          aria-label="Template kind"
          className="min-w-48"
          onChange={(event) => onKind(event.target.value as TemplateKind | "")}
          value={selectedKind}
        >
          <option value="">All template kinds</option>
          {templateKinds.map((kind) => (
            <option key={kind} value={kind}>
              {humanize(kind)}
            </option>
          ))}
        </Select>
        <Button onClick={onOpenForm}>
          <FileText aria-hidden="true" className="size-4" />
          {showForm ? "Close form" : "Add reviewed template"}
        </Button>
      </div>
      {showForm && (
        <TemplateCreateForm busy={busy("template")} onSubmit={onSubmit} />
      )}
      {templates.length === 0 ? (
        <EmptyState
          description="Create a reviewed local draft or change the current search and kind filters."
          title="No reviewed templates"
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {templates.map((template) => (
            <TemplateForm
              busy={busy(`template-${template.id}`)}
              key={`${template.id}-${template.version}`}
              onSubmit={(event) => onSave(template, event)}
              template={template}
            />
          ))}
        </div>
      )}
      {templateCursor && (
        <Button
          disabled={busy("more-templates")}
          onClick={onLoadMore}
          variant="secondary"
        >
          Load more templates
        </Button>
      )}
    </div>
  );
}

function TemplateCreateForm({
  busy,
  onSubmit,
}: {
  busy: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <form
      className="space-y-4 rounded-xl border border-line bg-surface p-4 sm:p-5"
      onSubmit={onSubmit}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <LabeledInput
          id="template-name"
          label="Template name"
          name="name"
          required
        />
        <label className="space-y-2 text-sm font-bold text-foreground">
          Kind
          <Select defaultValue="introduction" name="kind">
            {templateKinds.map((kind) => (
              <option key={kind} value={kind}>
                {humanize(kind)}
              </option>
            ))}
          </Select>
        </label>
      </div>
      <LabeledTextarea
        id="template-body"
        label="Local template text"
        maxLength={4000}
        name="body"
        required
      />
      <CheckboxField
        id="template-reviewed"
        label="I reviewed this text and understand Meridian will not send it"
        name="userReviewed"
        required
      />
      <Button disabled={busy} type="submit">
        {busy ? "Saving…" : "Save reviewed template"}
      </Button>
    </form>
  );
}

function TemplateForm({
  busy,
  onSubmit,
  template,
}: {
  busy: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  template: NetworkingTemplate;
}) {
  return (
    <form
      className="space-y-3 rounded-xl border border-line bg-surface p-4 shadow-sm"
      onSubmit={onSubmit}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <LabeledInput
          defaultValue={template.name}
          id={`template-${template.id}-name`}
          label="Name"
          name="name"
          required
        />
        <label className="space-y-2 text-sm font-bold text-foreground">
          Kind
          <Select defaultValue={template.kind} name="kind">
            {templateKinds.map((kind) => (
              <option key={kind} value={kind}>
                {humanize(kind)}
              </option>
            ))}
          </Select>
        </label>
      </div>
      <LabeledTextarea
        defaultValue={template.body}
        id={`template-${template.id}-body`}
        label="Local template text"
        maxLength={4000}
        name="body"
        required
      />
      <CheckboxField
        id={`template-${template.id}-reviewed`}
        label="I reviewed this edited text; no message will be sent"
        name="userReviewed"
        required
      />
      <Button disabled={busy} type="submit">
        {busy ? "Saving…" : "Save reviewed edit"}
      </Button>
    </form>
  );
}

function NetworkInput(props: React.ComponentProps<typeof Input>) {
  return <Input {...props} />;
}

function LabeledInput({
  id,
  label,
  ...props
}: React.ComponentProps<typeof Input> & { id: string; label: string }) {
  return (
    <label className="space-y-2 text-sm font-bold text-foreground" htmlFor={id}>
      {label}
      <Input id={id} {...props} />
    </label>
  );
}

function LabeledTextarea({
  id,
  label,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
  id: string;
  label: string;
}) {
  return (
    <label className="space-y-2 text-sm font-bold text-foreground" htmlFor={id}>
      {label}
      <textarea
        className="min-h-28 w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm font-normal text-foreground outline-none transition focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/25"
        id={id}
        {...props}
      />
    </label>
  );
}
