"use client";

import {
  ArrowLeft,
  CheckCircle2,
  Clock3,
  RefreshCcw,
  Save,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
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
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Input,
  LoadingSkeleton,
  Select,
  Tabs,
  buttonStyles,
} from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import { contactConsentPolicyVersion } from "../api/consent-policy";
import {
  ApiRequestError,
  createContactNote,
  createReferral,
  createReminder,
  deleteContact,
  getConsentHistory,
  getContact,
  getReminderExecutions,
  grantConsent,
  listContactNotes,
  listInteractions,
  listNetworkingApplications,
  listOrganizations,
  listReferrals,
  listReminders,
  listTemplates,
  recordInteraction,
  resolveReminder,
  updateContact,
  updateReferral,
  updateReminder,
  withdrawConsent,
} from "../api/networking-api";
import type {
  ApplicationSummary,
  ConsentEvent,
  ConsentPurpose,
  Contact,
  ContactNote,
  ContactReferralState,
  Interaction,
  InteractionCreateInput,
  InteractionDirection,
  InteractionKind,
  LocalReminderExecution,
  NetworkingTemplate,
  Organization,
  Referral,
  ReferralStatus,
  RelationshipStage,
  Reminder,
  ReminderResolutionInput,
  ReminderStatus,
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
const consentPurposes: readonly ConsentPurpose[] = [
  "collection",
  "storage",
  "outreach",
];
const interactionKinds: readonly InteractionKind[] = [
  "email",
  "call",
  "meeting",
  "message",
  "social",
  "referral",
  "other",
];
const interactionDirections: readonly InteractionDirection[] = [
  "inbound",
  "outbound",
  "mutual",
];
const referralStatuses: readonly ReferralStatus[] = [
  "planned",
  "requested",
  "referred",
  "declined",
  "cancelled",
];
const reminderStatuses: readonly ReminderStatus[] = [
  "active",
  "completed",
  "cancelled",
];

function humanize(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function dateTime(value: string | null): string {
  if (!value) return "Not recorded";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function localDateTime(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function splitTags(value: FormDataEntryValue | null): string[] {
  return String(value ?? "")
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function includesQuery(value: string, query: string): boolean {
  return value.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());
}

function uniqueById<T extends { id: string }>(values: readonly T[]): T[] {
  const seen = new Set<string>();
  return values.filter((value) => {
    if (seen.has(value.id)) return false;
    seen.add(value.id);
    return true;
  });
}

function applicationLabel(application: ApplicationSummary): string {
  return [application.jobTitle, application.company]
    .filter(Boolean)
    .join(" — ");
}

type ContactState =
  | { status: "loading" }
  | {
      applications: ApplicationSummary[];
      applicationCursor: string | null;
      consentCursor: string | null;
      consentEvents: ConsentEvent[];
      contact: Contact;
      executions: Record<string, LocalReminderExecution | null>;
      interactions: Interaction[];
      interactionCursor: string | null;
      loadedTabs: Record<string, boolean>;
      noteCursor: string | null;
      notes: ContactNote[];
      organizations: Organization[];
      organizationCursor: string | null;
      referralCursor: string | null;
      referrals: Referral[];
      reminderCursor: string | null;
      reminders: Reminder[];
      status: "ready";
      templateCursor: string | null;
      templates: NetworkingTemplate[];
    }
  | { message: string; status: "error" };

export function ContactDetailView({ contactId }: { contactId: string }) {
  const router = useRouter();
  const [state, setState] = useState<ContactState>({ status: "loading" });
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const {
    begin: beginActivity,
    finish: finishActivity,
    isBusy,
  } = useIntentActivity();
  const [executionBusy, setExecutionBusy] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const requestEpoch = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const executionEpoch = useRef(0);
  const executionController = useRef<AbortController | null>(null);
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
      executionController.current?.abort();
      executionEpoch.current += 1;
      setExecutionBusy(false);
      const nextController = new AbortController();
      controller.current = nextController;
      const epoch = ++requestEpoch.current;
      setFailure(undefined);
      try {
        const [contact, organizations] = await Promise.all([
          getContact(contactId, nextController.signal),
          listOrganizations({ limit: 50, signal: nextController.signal }),
        ]);
        if (epoch !== requestEpoch.current || nextController.signal.aborted)
          return;
        setState({
          applications: [],
          applicationCursor: null,
          consentCursor: null,
          consentEvents: [],
          contact,
          executions: {},
          interactions: [],
          interactionCursor: null,
          loadedTabs: { overview: true },
          noteCursor: null,
          notes: [],
          organizationCursor: organizations.page.nextCursor,
          organizations: organizations.data,
          referralCursor: null,
          referrals: [],
          reminderCursor: null,
          reminders: [],
          status: "ready",
          templateCursor: null,
          templates: [],
        });
        if (authoritativeMessage) setFailure(authoritativeMessage);
      } catch (error) {
        if (epoch !== requestEpoch.current || nextController.signal.aborted)
          return;
        setState({
          message: requestErrorMessage(
            error,
            "The private contact record could not be loaded.",
          ),
          status: "error",
        });
      }
    },
    [contactId],
  );

  const loadExecutions = useCallback(async (reminders: Reminder[]) => {
    executionController.current?.abort();
    const nextController = new AbortController();
    executionController.current = nextController;
    const epoch = ++executionEpoch.current;
    const rootEpoch = requestEpoch.current;
    setExecutionBusy(true);
    try {
      const response = await getReminderExecutions(
        reminders.map((reminder) => reminder.id),
        nextController.signal,
      );
      const loaded = new Map(
        response.data.map((item) => [item.reminderId, item.execution]),
      );
      const entries = reminders.map(
        (reminder) => [reminder.id, loaded.get(reminder.id) ?? null] as const,
      );
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              executions: {
                ...current.executions,
                ...Object.fromEntries(entries),
              },
            }
          : current,
      );
    } catch (error) {
      if (
        nextController.signal.aborted ||
        epoch !== executionEpoch.current ||
        rootEpoch !== requestEpoch.current
      ) {
        return;
      }
      setFailure(
        requestErrorMessage(
          error,
          "Local reminder execution state could not be loaded.",
        ),
      );
    } finally {
      if (epoch === executionEpoch.current) setExecutionBusy(false);
    }
  }, []);

  const loadingTabs = useRef(new Set<string>());

  const loadTab = useCallback(
    async (tab: string) => {
      if (tab === "overview" || loadingTabs.current.has(tab)) return;
      loadingTabs.current.add(tab);
      const epoch = requestEpoch.current;
      setFailure(undefined);
      try {
        if (tab === "consent") {
          const consent = await getConsentHistory(contactId, { limit: 100 });
          if (epoch !== requestEpoch.current) return;
          setState((current) =>
            current.status === "ready"
              ? {
                  ...current,
                  consentCursor: consent.page.nextCursor,
                  consentEvents: consent.events,
                  loadedTabs: { ...current.loadedTabs, consent: true },
                }
              : current,
          );
        } else if (tab === "notes") {
          const notes = await listContactNotes(contactId, { limit: 100 });
          if (epoch !== requestEpoch.current) return;
          setState((current) =>
            current.status === "ready"
              ? {
                  ...current,
                  loadedTabs: { ...current.loadedTabs, notes: true },
                  noteCursor: notes.page.nextCursor,
                  notes: notes.data,
                }
              : current,
          );
        } else if (tab === "interactions") {
          const [interactions, templates] = await Promise.all([
            listInteractions(contactId, { limit: 100 }),
            listTemplates({ limit: 100 }),
          ]);
          if (epoch !== requestEpoch.current) return;
          setState((current) =>
            current.status === "ready"
              ? {
                  ...current,
                  interactionCursor: interactions.page.nextCursor,
                  interactions: interactions.data,
                  loadedTabs: { ...current.loadedTabs, interactions: true },
                  templateCursor: templates.page.nextCursor,
                  templates: templates.data,
                }
              : current,
          );
        } else if (tab === "referrals") {
          const [referrals, applications] = await Promise.all([
            listReferrals(contactId, { limit: 100 }),
            listNetworkingApplications({ limit: 100 }),
          ]);
          if (epoch !== requestEpoch.current) return;
          setState((current) =>
            current.status === "ready"
              ? {
                  ...current,
                  applicationCursor: applications.page.nextCursor,
                  applications: applications.data,
                  loadedTabs: { ...current.loadedTabs, referrals: true },
                  referralCursor: referrals.page.nextCursor,
                  referrals: referrals.data,
                }
              : current,
          );
        } else if (tab === "reminders") {
          const reminders = await listReminders(contactId, { limit: 100 });
          if (epoch !== requestEpoch.current) return;
          setState((current) =>
            current.status === "ready"
              ? {
                  ...current,
                  loadedTabs: { ...current.loadedTabs, reminders: true },
                  reminderCursor: reminders.page.nextCursor,
                  reminders: reminders.data,
                }
              : current,
          );
        }
      } catch (error) {
        if (epoch !== requestEpoch.current) return;
        setFailure(
          requestErrorMessage(
            error,
            `The ${tab} collection could not be loaded.`,
          ),
        );
      } finally {
        loadingTabs.current.delete(tab);
      }
    },
    [contactId],
  );

  useEffect(() => {
    queueMicrotask(() => void load());
    return () => {
      controller.current?.abort();
      executionController.current?.abort();
      requestEpoch.current += 1;
      executionEpoch.current += 1;
    };
  }, [load]);

  useEffect(() => {
    if (
      state.status !== "ready" ||
      state.loadedTabs[activeTab] ||
      loadingTabs.current.has(activeTab)
    ) {
      return;
    }
    queueMicrotask(() => void loadTab(activeTab));
  }, [activeTab, loadTab, state]);

  const missingExecutions = useMemo(
    () =>
      state.status === "ready" && activeTab === "reminders"
        ? state.reminders.filter(
            (reminder) => !(reminder.id in state.executions),
          )
        : [],
    [activeTab, state],
  );

  useEffect(() => {
    if (missingExecutions.length === 0) return;
    queueMicrotask(() => void loadExecutions(missingExecutions));
  }, [loadExecutions, missingExecutions]);

  async function loadMore(
    collection:
      | "consent"
      | "notes"
      | "interactions"
      | "referrals"
      | "reminders"
      | "templates"
      | "organizations"
      | "applications",
  ) {
    if (state.status !== "ready") return;
    const cursor =
      collection === "consent"
        ? state.consentCursor
        : collection === "notes"
          ? state.noteCursor
          : collection === "interactions"
            ? state.interactionCursor
            : collection === "referrals"
              ? state.referralCursor
              : collection === "reminders"
                ? state.reminderCursor
                : collection === "templates"
                  ? state.templateCursor
                  : collection === "organizations"
                    ? state.organizationCursor
                    : state.applicationCursor;
    if (!cursor) return;
    const activityKey = `more-${collection}`;
    const activityEpoch = beginActivity(activityKey);
    if (activityEpoch === null) return;
    const epoch = requestEpoch.current;
    setFailure(undefined);
    try {
      if (collection === "consent") {
        const page = await getConsentHistory(contactId, { cursor, limit: 100 });
        if (epoch !== requestEpoch.current) return;
        setState((current) =>
          current.status === "ready" && current.consentCursor === cursor
            ? {
                ...current,
                consentCursor: page.page.nextCursor,
                consentEvents: uniqueById([
                  ...current.consentEvents,
                  ...page.events,
                ]),
              }
            : current,
        );
      } else if (collection === "notes") {
        const page = await listContactNotes(contactId, { cursor, limit: 100 });
        if (epoch !== requestEpoch.current) return;
        setState((current) =>
          current.status === "ready" && current.noteCursor === cursor
            ? {
                ...current,
                noteCursor: page.page.nextCursor,
                notes: uniqueById([...current.notes, ...page.data]),
              }
            : current,
        );
      } else if (collection === "interactions") {
        const page = await listInteractions(contactId, { cursor, limit: 100 });
        if (epoch !== requestEpoch.current) return;
        setState((current) =>
          current.status === "ready" && current.interactionCursor === cursor
            ? {
                ...current,
                interactionCursor: page.page.nextCursor,
                interactions: uniqueById([
                  ...current.interactions,
                  ...page.data,
                ]),
              }
            : current,
        );
      } else if (collection === "referrals") {
        const page = await listReferrals(contactId, { cursor, limit: 100 });
        if (epoch !== requestEpoch.current) return;
        setState((current) =>
          current.status === "ready" && current.referralCursor === cursor
            ? {
                ...current,
                referralCursor: page.page.nextCursor,
                referrals: uniqueById([...current.referrals, ...page.data]),
              }
            : current,
        );
      } else if (collection === "reminders") {
        const page = await listReminders(contactId, { cursor, limit: 100 });
        if (epoch !== requestEpoch.current) return;
        setState((current) =>
          current.status === "ready" && current.reminderCursor === cursor
            ? {
                ...current,
                reminderCursor: page.page.nextCursor,
                reminders: uniqueById([...current.reminders, ...page.data]),
              }
            : current,
        );
      } else if (collection === "templates") {
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
      } else if (collection === "organizations") {
        const page = await listOrganizations({ cursor, limit: 100 });
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
        const page = await listNetworkingApplications({ cursor, limit: 100 });
        if (epoch !== requestEpoch.current) return;
        setState((current) =>
          current.status === "ready" && current.applicationCursor === cursor
            ? {
                ...current,
                applicationCursor: page.page.nextCursor,
                applications: uniqueById([
                  ...current.applications,
                  ...page.data,
                ]),
              }
            : current,
        );
      }
    } catch (error) {
      if (epoch !== requestEpoch.current) return;
      setFailure(
        requestErrorMessage(
          error,
          `More ${collection} records could not be loaded.`,
        ),
      );
    } finally {
      finishActivity(activityKey, activityEpoch);
    }
  }

  async function saveContact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.status !== "ready") return;
    const form = new FormData(event.currentTarget);
    const nextContactAt = String(form.get("nextContactAt") ?? "");
    const input = {
      email: String(form.get("email") ?? "").trim() || null,
      location: String(form.get("location") ?? "").trim() || null,
      name: String(form.get("name") ?? "").trim(),
      nextContactAt: nextContactAt
        ? new Date(nextContactAt).toISOString()
        : null,
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
    const intent = `contact-update:${contactId}:${state.contact.version}:${JSON.stringify(input)}`;
    const activityEpoch = beginActivity("contact");
    if (activityEpoch === null) return;
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const contact = await updateContact(
        state.contact,
        input,
        stableIntent(intent),
      );
      clearIntent(intent);
      setState((current) =>
        current.status === "ready" ? { ...current, contact } : current,
      );
      setSuccess("Private contact details updated.");
    } catch (error) {
      await conflictOrFailure(
        error,
        "The contact could not be updated.",
        "This contact changed in another session. The authoritative private record and child collections were reloaded.",
      );
    } finally {
      finishActivity("contact", activityEpoch);
    }
  }

  async function changeConsent(
    action: "grant" | "withdraw",
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    if (state.status !== "ready") return;
    const form = new FormData(event.currentTarget);
    const input = {
      policyVersion: contactConsentPolicyVersion,
      purpose: String(form.get("purpose")) as ConsentPurpose,
    };
    const intent = `consent-${action}:${contactId}:${state.contact.version}:${JSON.stringify(input)}`;
    const activityKey = `consent-${action}`;
    const activityEpoch = beginActivity(activityKey);
    if (activityEpoch === null) return;
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const contact =
        action === "grant"
          ? await grantConsent(state.contact, input, stableIntent(intent))
          : await withdrawConsent(state.contact, input, stableIntent(intent));
      clearIntent(intent);
      if (
        action === "withdraw" &&
        (input.purpose === "collection" || input.purpose === "storage")
      ) {
        router.replace("/networking");
        router.refresh();
        return;
      }
      await load();
      setSuccess(
        `${humanize(input.purpose)} consent ${action === "grant" ? "granted" : "withdrawn"} and recorded in the append-only history.`,
      );
      setState((current) =>
        current.status === "ready" ? { ...current, contact } : current,
      );
    } catch (error) {
      await conflictOrFailure(
        error,
        "Consent could not be changed.",
        "Consent changed in another session. The authoritative consent ledger was reloaded.",
      );
    } finally {
      finishActivity(activityKey, activityEpoch);
    }
  }

  async function addNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const input = {
      body: String(new FormData(formElement).get("body") ?? "").trim(),
    };
    const intent = `note:${contactId}:${JSON.stringify(input)}`;
    const activityEpoch = beginActivity("note");
    if (activityEpoch === null) return;
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const note = await createContactNote(
        contactId,
        input,
        stableIntent(intent),
      );
      clearIntent(intent);
      setState((current) =>
        current.status === "ready"
          ? { ...current, notes: uniqueById([note, ...current.notes]) }
          : current,
      );
      setSuccess("Private relationship note saved.");
      formElement.reset();
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "The private note could not be saved."),
      );
    } finally {
      finishActivity("note", activityEpoch);
    }
  }

  async function addInteraction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.status !== "ready" || !state.contact.consent.allowsOutreach)
      return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const occurredAt = String(form.get("occurredAt") ?? "");
    const input: InteractionCreateInput = {
      direction: String(form.get("direction")) as InteractionDirection,
      kind: String(form.get("kind")) as InteractionKind,
      occurredAt: new Date(occurredAt).toISOString(),
      summary: String(form.get("summary") ?? "").trim(),
      templateId: String(form.get("templateId") ?? "") || null,
    };
    const intent = `interaction:${contactId}:${state.contact.version}:${JSON.stringify(input)}`;
    const activityEpoch = beginActivity("interaction");
    if (activityEpoch === null) return;
    setFailure(undefined);
    setSuccess(undefined);
    try {
      await recordInteraction(state.contact, input, stableIntent(intent));
      clearIntent(intent);
      await load();
      setSuccess(
        "Interaction recorded as local history only. CareerOS did not send anything.",
      );
      formElement.reset();
    } catch (error) {
      await conflictOrFailure(
        error,
        "The interaction could not be recorded.",
        "The contact changed elsewhere. The authoritative private record was reloaded.",
      );
    } finally {
      finishActivity("interaction", activityEpoch);
    }
  }

  async function addReferral(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.status !== "ready" || !state.contact.consent.allowsOutreach)
      return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const input = {
      applicationId: String(form.get("applicationId") ?? ""),
      context: String(form.get("context") ?? "").trim() || null,
      status: String(form.get("status")) as ReferralStatus,
    };
    const intent = `referral:${contactId}:${state.contact.version}:${JSON.stringify(input)}`;
    const activityEpoch = beginActivity("referral");
    if (activityEpoch === null) return;
    setFailure(undefined);
    setSuccess(undefined);
    try {
      await createReferral(state.contact, input, stableIntent(intent));
      clearIntent(intent);
      await load();
      setSuccess("Referral state recorded locally. No request was sent.");
      formElement.reset();
    } catch (error) {
      await conflictOrFailure(
        error,
        "The referral could not be recorded.",
        "The contact changed elsewhere. The authoritative private record was reloaded.",
      );
    } finally {
      finishActivity("referral", activityEpoch);
    }
  }

  async function saveReferral(
    referral: Referral,
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const input = {
      context: String(form.get("context") ?? "").trim() || null,
      status: String(form.get("status")) as ReferralStatus,
    };
    const intent = `referral-update:${referral.id}:${referral.version}:${JSON.stringify(input)}`;
    const activityKey = `referral-${referral.id}`;
    const activityEpoch = beginActivity(activityKey);
    if (activityEpoch === null) return;
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const updated = await updateReferral(
        referral,
        input,
        stableIntent(intent),
      );
      clearIntent(intent);
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              referrals: current.referrals.map((item) =>
                item.id === updated.id ? updated : item,
              ),
            }
          : current,
      );
      setSuccess("Referral state updated locally.");
    } catch (error) {
      await conflictOrFailure(
        error,
        "The referral could not be updated.",
        "The referral changed elsewhere. The authoritative private record was reloaded.",
      );
    } finally {
      finishActivity(activityKey, activityEpoch);
    }
  }

  async function addReminder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.status !== "ready" || !state.contact.consent.allowsOutreach)
      return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const dueAt = String(form.get("dueAt") ?? "");
    const recurrence = String(form.get("recurrenceDays") ?? "");
    const input = {
      dueAt: new Date(dueAt).toISOString(),
      maxAttempts: Number(form.get("maxAttempts")),
      recurrenceDays: recurrence ? Number(recurrence) : null,
      title: String(form.get("title") ?? "").trim(),
    };
    const intent = `reminder:${contactId}:${JSON.stringify(input)}`;
    const activityEpoch = beginActivity("reminder");
    if (activityEpoch === null) return;
    setFailure(undefined);
    setSuccess(undefined);
    try {
      await createReminder(contactId, input, stableIntent(intent));
      clearIntent(intent);
      await load();
      setSuccess(
        "Local reminder created. It will never email, message, or push this contact.",
      );
      formElement.reset();
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "The local reminder could not be created."),
      );
    } finally {
      finishActivity("reminder", activityEpoch);
    }
  }

  async function saveReminder(
    reminder: Reminder,
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const recurrence = String(form.get("recurrenceDays") ?? "");
    const input = {
      dueAt: new Date(String(form.get("dueAt"))).toISOString(),
      recurrenceDays: recurrence ? Number(recurrence) : null,
      status: String(form.get("status")) as ReminderStatus,
      title: String(form.get("title") ?? "").trim(),
    };
    const intent = `reminder-update:${reminder.id}:${reminder.version}:${JSON.stringify(input)}`;
    const activityKey = `reminder-${reminder.id}`;
    const activityEpoch = beginActivity(activityKey);
    if (activityEpoch === null) return;
    setFailure(undefined);
    setSuccess(undefined);
    try {
      await updateReminder(reminder, input, stableIntent(intent));
      clearIntent(intent);
      await load();
      setSuccess("Local reminder state updated.");
    } catch (error) {
      await conflictOrFailure(
        error,
        "The local reminder could not be updated.",
        "The reminder changed elsewhere. Authoritative reminder and execution state was reloaded.",
      );
    } finally {
      finishActivity(activityKey, activityEpoch);
    }
  }

  async function resolveDueReminder(
    reminder: Reminder,
    input: ReminderResolutionInput,
  ) {
    const activityKey = `reminder-action-${reminder.id}`;
    const activityEpoch = beginActivity(activityKey);
    if (activityEpoch === null) return;
    const intent = `reminder-action:${reminder.id}:${reminder.version}:${JSON.stringify(input)}`;
    setFailure(undefined);
    setSuccess(undefined);
    try {
      await resolveReminder(reminder, input, stableIntent(intent));
      clearIntent(intent);
      await load();
      setSuccess(
        input.action === "snooze"
          ? "Reminder snoozed. A new local occurrence was scheduled."
          : input.action === "complete"
            ? "Reminder completed by you."
            : "Reminder acknowledged by you.",
      );
    } catch (error) {
      await conflictOrFailure(
        error,
        "The due reminder action could not be saved.",
        "The reminder changed elsewhere. Authoritative reminder state was reloaded.",
      );
    } finally {
      finishActivity(activityKey, activityEpoch);
    }
  }

  async function removeContact() {
    if (state.status !== "ready") return;
    const intent = `contact-delete:${contactId}:${state.contact.version}`;
    const activityEpoch = beginActivity("delete");
    if (activityEpoch === null) return;
    setFailure(undefined);
    try {
      await deleteContact(state.contact, stableIntent(intent));
      clearIntent(intent);
      router.replace("/networking");
      router.refresh();
    } catch (error) {
      setDeleteOpen(false);
      await conflictOrFailure(
        error,
        "The contact could not be deleted.",
        "The contact changed elsewhere. The authoritative private record was reloaded and was not deleted.",
      );
    } finally {
      finishActivity("delete", activityEpoch);
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
          title="Private contact unavailable"
        />
      </main>
    );
  }

  if (state.status === "loading") {
    return (
      <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
        <LoadingSkeleton />
      </main>
    );
  }

  return (
    <main
      className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8"
      id="main-content"
    >
      <Link
        className={`${buttonStyles.base} ${buttonStyles.ghost} -ml-3`}
        href="/networking"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Networking
      </Link>

      <header className="rounded-card border border-border bg-surface-raised p-4 sm:p-5">
        <div className="flex flex-wrap gap-2">
          <Badge tone="primary">
            {humanize(state.contact.relationshipStage)}
          </Badge>
          <Badge
            tone={state.contact.consent.allowsOutreach ? "success" : "warning"}
          >
            Outreach{" "}
            {state.contact.consent.allowsOutreach ? "allowed" : "blocked"}
          </Badge>
          <Badge tone="neutral">Private contact</Badge>
        </div>
        <h1 className="mt-3 text-2xl font-black text-foreground">
          {state.contact.name}
        </h1>
        <p className="mt-1 text-sm text-muted">
          {[state.contact.role, state.contact.location]
            .filter(Boolean)
            .join(" · ") || "Role and location not recorded"}
        </p>
        <p className="mt-3 text-xs font-semibold text-muted">
          Last contact: {dateTime(state.contact.lastContactAt)} · Next contact:{" "}
          {dateTime(state.contact.nextContactAt)} · Version{" "}
          {state.contact.version}
        </p>
      </header>

      <Alert title="Private and local-only" tone="warning">
        CareerOS stores this record only for the account owner. It does not
        scrape, fetch the profile URL, import contacts, send messages, or
        deliver reminders externally.
      </Alert>

      {failure && (
        <Alert title="Review current data" tone="danger">
          <p>{failure}</p>
          <Button
            className="mt-3 min-h-9 px-3"
            onClick={() => void load()}
            variant="secondary"
          >
            <RefreshCcw aria-hidden="true" className="size-4" />
            Reload authoritative data
          </Button>
        </Alert>
      )}
      {success && (
        <Alert title="Contact workspace updated" tone="success">
          {success}
        </Alert>
      )}

      <Tabs
        label="Private contact record"
        onValueChange={setActiveTab}
        tabs={[
          {
            id: "overview",
            label: "Overview",
            panel: (
              <OverviewPanel
                busy={isBusy}
                contact={state.contact}
                onDelete={() => setDeleteOpen(true)}
                onLoadOrganizations={() => void loadMore("organizations")}
                onSubmit={saveContact}
                organizationCursor={state.organizationCursor}
                organizations={state.organizations}
              />
            ),
          },
          {
            id: "consent",
            label: `Consent history (${state.consentEvents.length})`,
            panel: (
              <ConsentPanel
                busy={isBusy}
                consentCursor={state.consentCursor}
                contact={state.contact}
                events={state.consentEvents}
                onChange={(action, event) => void changeConsent(action, event)}
                onLoadMore={() => void loadMore("consent")}
              />
            ),
          },
          {
            id: "notes",
            label: `Notes (${state.notes.length})`,
            panel: (
              <NotesPanel
                busy={isBusy}
                noteCursor={state.noteCursor}
                notes={state.notes}
                onLoadMore={() => void loadMore("notes")}
                onSubmit={addNote}
              />
            ),
          },
          {
            id: "interactions",
            label: `Interactions (${state.interactions.length})`,
            panel: (
              <InteractionsPanel
                busy={isBusy}
                contact={state.contact}
                interactionCursor={state.interactionCursor}
                interactions={state.interactions}
                onLoadMore={() => void loadMore("interactions")}
                onLoadTemplates={() => void loadMore("templates")}
                onSubmit={addInteraction}
                templateCursor={state.templateCursor}
                templates={state.templates}
              />
            ),
          },
          {
            id: "referrals",
            label: `Referrals (${state.referrals.length})`,
            panel: (
              <ReferralsPanel
                applicationCursor={state.applicationCursor}
                applications={state.applications}
                busy={isBusy}
                contact={state.contact}
                onCreate={addReferral}
                onLoadApplications={() => void loadMore("applications")}
                onLoadMore={() => void loadMore("referrals")}
                onSave={(referral, event) => void saveReferral(referral, event)}
                referralCursor={state.referralCursor}
                referrals={state.referrals}
              />
            ),
          },
          {
            id: "reminders",
            label: `Local reminders (${state.reminders.length})`,
            panel: (
              <RemindersPanel
                busy={isBusy}
                contact={state.contact}
                executionBusy={executionBusy}
                executions={state.executions}
                onCreate={addReminder}
                onLoadMore={() => void loadMore("reminders")}
                onResolve={(reminder, input) =>
                  void resolveDueReminder(reminder, input)
                }
                onSave={(reminder, event) => void saveReminder(reminder, event)}
                reminderCursor={state.reminderCursor}
                reminders={state.reminders}
              />
            ),
          },
        ]}
        value={activeTab}
      />

      <ConfirmDialog
        confirmLabel="Delete private contact"
        description="Personal content is redacted and outreach-related local reminders are cancelled. Only minimum content-free audit and idempotency records remain."
        loading={isBusy("delete")}
        onConfirm={() => void removeContact()}
        onOpenChange={setDeleteOpen}
        open={deleteOpen}
        title={`Delete ${state.contact.name}?`}
      />
    </main>
  );
}

function OverviewPanel({
  busy,
  contact,
  onDelete,
  onLoadOrganizations,
  onSubmit,
  organizationCursor,
  organizations,
}: {
  busy: (key: string) => boolean;
  contact: Contact;
  onDelete: () => void;
  onLoadOrganizations: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  organizationCursor: string | null;
  organizations: Organization[];
}) {
  return (
    <div className="space-y-5 pt-5">
      <form
        className="grid gap-4 rounded-xl border border-line bg-white p-4 shadow-sm sm:grid-cols-2 lg:grid-cols-3 sm:p-5"
        key={contact.version}
        onSubmit={onSubmit}
      >
        <LabeledInput
          defaultValue={contact.name}
          id="contact-detail-name"
          label="Name"
          name="name"
          required
        />
        <LabeledInput
          defaultValue={contact.role ?? ""}
          id="contact-detail-role"
          label="Role"
          name="role"
        />
        <label className="space-y-2 text-sm font-bold text-foreground">
          Organization
          <Select
            defaultValue={contact.organizationId ?? ""}
            name="organizationId"
          >
            <option value="">No organization</option>
            {organizations.map((organization) => (
              <option key={organization.id} value={organization.id}>
                {organization.name}
              </option>
            ))}
          </Select>
          {organizationCursor && (
            <Button
              className="min-h-9 px-3"
              disabled={busy("more-organizations")}
              onClick={onLoadOrganizations}
              type="button"
              variant="ghost"
            >
              Load more organizations
            </Button>
          )}
        </label>
        <LabeledInput
          defaultValue={contact.email ?? ""}
          id="contact-detail-email"
          label="Email"
          name="email"
          type="email"
        />
        <LabeledInput
          defaultValue={contact.phone ?? ""}
          id="contact-detail-phone"
          label="Phone"
          name="phone"
        />
        <LabeledInput
          defaultValue={contact.profileUrl ?? ""}
          id="contact-detail-profile"
          label="Profile URL (stored only)"
          name="profileUrl"
          type="url"
        />
        <LabeledInput
          defaultValue={contact.location ?? ""}
          id="contact-detail-location"
          label="Location"
          name="location"
        />
        <label className="space-y-2 text-sm font-bold text-foreground">
          Relationship stage
          <Select
            defaultValue={contact.relationshipStage}
            name="relationshipStage"
          >
            {relationshipStages.map((stage) => (
              <option key={stage} value={stage}>
                {humanize(stage)}
              </option>
            ))}
          </Select>
        </label>
        <label className="space-y-2 text-sm font-bold text-foreground">
          Referral state
          <Select defaultValue={contact.referralState} name="referralState">
            {contactReferralStates.map((status) => (
              <option key={status} value={status}>
                {humanize(status)}
              </option>
            ))}
          </Select>
        </label>
        <LabeledInput
          defaultValue={contact.tags.join(", ")}
          id="contact-detail-tags"
          label="Tags (comma separated)"
          name="tags"
        />
        <LabeledInput
          defaultValue={localDateTime(contact.nextContactAt)}
          id="contact-detail-next"
          label="Next contact time"
          name="nextContactAt"
          type="datetime-local"
        />
        <div className="flex items-end gap-2">
          <Button disabled={busy("contact")} type="submit">
            <Save aria-hidden="true" className="size-4" />
            {busy("contact") ? "Saving…" : "Save details"}
          </Button>
          <Button onClick={onDelete} type="button" variant="danger">
            <Trash2 aria-hidden="true" className="size-4" />
            Delete
          </Button>
        </div>
      </form>
    </div>
  );
}

function ConsentPanel({
  busy,
  consentCursor,
  contact,
  events,
  onChange,
  onLoadMore,
}: {
  busy: (key: string) => boolean;
  consentCursor: string | null;
  contact: Contact;
  events: ConsentEvent[];
  onChange: (
    action: "grant" | "withdraw",
    event: FormEvent<HTMLFormElement>,
  ) => void;
  onLoadMore: () => void;
}) {
  const [query, setQuery] = useState("");
  const [purpose, setPurpose] = useState<ConsentPurpose | "">("");
  const [action, setAction] = useState<ConsentEvent["action"] | "">("");
  const visible = events.filter(
    (event) =>
      (!purpose || event.purpose === purpose) &&
      (!action || event.action === action) &&
      (!query ||
        includesQuery(
          `${event.purpose} ${event.action} ${event.policyVersion} ${event.sequence}`,
          query,
        )),
  );
  return (
    <div className="space-y-5 pt-5">
      <div className="grid gap-3 sm:grid-cols-3">
        {consentPurposes.map((item) => {
          const granted = contact.consent[item];
          return (
            <div
              className="rounded-xl border border-line bg-white p-4"
              key={item}
            >
              <p className="text-xs font-bold uppercase tracking-wide text-muted">
                {humanize(item)}
              </p>
              <p className="mt-2 flex items-center gap-2 font-black text-foreground">
                {granted ? (
                  <CheckCircle2
                    aria-hidden="true"
                    className="size-4 text-success"
                  />
                ) : (
                  <ShieldAlert
                    aria-hidden="true"
                    className="size-4 text-warning"
                  />
                )}
                {granted ? "Granted" : "Not granted"}
              </p>
            </div>
          );
        })}
      </div>
      <Alert title="Append-only consent history" tone="info">
        Collection, storage, and outreach are separate purposes. Withdrawing
        outreach immediately blocks and redacts outbound interactions,
        referrals, and reminders while preserving locally stored notes and
        inbound history. Withdrawing collection or storage permanently redacts
        this contact and its private content, then returns you to the Networking
        workspace.
      </Alert>
      <div className="grid gap-4 lg:grid-cols-2">
        {(["grant", "withdraw"] as const).map((change) => (
          <form
            className="space-y-3 rounded-xl border border-line bg-white p-4"
            key={change}
            onSubmit={(event) => onChange(change, event)}
          >
            <h2 className="font-black text-foreground">
              {change === "grant" ? "Grant consent" : "Withdraw consent"}
            </h2>
            <label className="space-y-2 text-sm font-bold text-foreground">
              Purpose
              <Select defaultValue="outreach" name="purpose">
                {consentPurposes.map((item) => (
                  <option key={item} value={item}>
                    {humanize(item)}
                  </option>
                ))}
              </Select>
            </label>
            <p className="text-sm text-muted">
              Policy version:{" "}
              <span className="font-semibold text-foreground">
                {contactConsentPolicyVersion}
              </span>
            </p>
            <Button
              disabled={busy(`consent-${change}`)}
              type="submit"
              variant={change === "withdraw" ? "danger" : "primary"}
            >
              {change === "grant" ? "Record grant" : "Record withdrawal"}
            </Button>
          </form>
        ))}
      </div>
      <CollectionFilter
        filters={[
          {
            label: "Purpose",
            onChange: (value) => setPurpose(value as ConsentPurpose | ""),
            options: consentPurposes,
            value: purpose,
          },
          {
            label: "Action",
            onChange: (value) =>
              setAction(value as ConsentEvent["action"] | ""),
            options: ["granted", "withdrawn"],
            value: action,
          },
        ]}
        onQuery={setQuery}
        query={query}
        searchLabel="Search consent history"
      />
      {visible.length === 0 ? (
        <EmptyState
          description="No loaded consent events match the current search and filters."
          title="No consent history matches"
        />
      ) : (
        <ol className="space-y-3">
          {visible.map((event) => (
            <li
              className="rounded-xl border border-line bg-white p-4"
              key={event.id}
            >
              <div className="flex flex-wrap gap-2">
                <Badge
                  tone={event.action === "granted" ? "success" : "warning"}
                >
                  {humanize(event.action)}
                </Badge>
                <Badge tone="neutral">{humanize(event.purpose)}</Badge>
              </div>
              <p className="mt-2 text-sm text-muted">
                Sequence {event.sequence} · Policy {event.policyVersion} ·{" "}
                {dateTime(event.occurredAt)}
              </p>
            </li>
          ))}
        </ol>
      )}
      {consentCursor && (
        <Button
          disabled={busy("more-consent")}
          onClick={onLoadMore}
          variant="secondary"
        >
          Load more consent history
        </Button>
      )}
    </div>
  );
}

function NotesPanel({
  busy,
  noteCursor,
  notes,
  onLoadMore,
  onSubmit,
}: {
  busy: (key: string) => boolean;
  noteCursor: string | null;
  notes: ContactNote[];
  onLoadMore: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const [query, setQuery] = useState("");
  const visible = notes.filter(
    (note) => !query || includesQuery(note.body, query),
  );
  return (
    <div className="space-y-5 pt-5">
      <Alert title="Private notes" tone="info">
        Relationship notes stay private and are not generation, analytics, or
        outreach input.
      </Alert>
      <form
        className="space-y-3 rounded-xl border border-line bg-white p-4"
        onSubmit={onSubmit}
      >
        <LabeledTextarea
          id="contact-note"
          label="Private note"
          maxLength={4000}
          name="body"
          required
        />
        <Button disabled={busy("note")} type="submit">
          {busy("note") ? "Saving…" : "Save private note"}
        </Button>
      </form>
      <CollectionFilter
        onQuery={setQuery}
        query={query}
        searchLabel="Search loaded private notes"
      />
      {visible.length === 0 ? (
        <EmptyState
          description="No loaded private notes match the current search."
          title="No private notes match"
        />
      ) : (
        <ul className="space-y-3">
          {visible.map((note) => (
            <li
              className="rounded-xl border border-line bg-white p-4"
              key={note.id}
            >
              <p className="whitespace-pre-wrap text-sm leading-6 text-foreground">
                {note.body}
              </p>
              <p className="mt-2 text-xs text-muted">
                Saved {dateTime(note.createdAt)}
              </p>
            </li>
          ))}
        </ul>
      )}
      {noteCursor && (
        <Button
          disabled={busy("more-notes")}
          onClick={onLoadMore}
          variant="secondary"
        >
          Load more notes
        </Button>
      )}
    </div>
  );
}

function InteractionsPanel({
  busy,
  contact,
  interactionCursor,
  interactions,
  onLoadMore,
  onLoadTemplates,
  onSubmit,
  templateCursor,
  templates,
}: {
  busy: (key: string) => boolean;
  contact: Contact;
  interactionCursor: string | null;
  interactions: Interaction[];
  onLoadMore: () => void;
  onLoadTemplates: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  templateCursor: string | null;
  templates: NetworkingTemplate[];
}) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<InteractionKind | "">("");
  const [direction, setDirection] = useState<InteractionDirection | "">("");
  const visible = interactions.filter(
    (interaction) =>
      (!kind || interaction.kind === kind) &&
      (!direction || interaction.direction === direction) &&
      (!query ||
        includesQuery(
          `${interaction.summary} ${interaction.kind} ${interaction.direction}`,
          query,
        )),
  );
  return (
    <div className="space-y-5 pt-5">
      {!contact.consent.allowsOutreach && (
        <Alert title="Outreach consent required" tone="danger">
          New interaction history is blocked because current outreach consent is
          not granted. Record a purpose-scoped consent grant first.
        </Alert>
      )}
      <Alert title="History only — nothing is sent" tone="warning">
        Record an interaction that happened elsewhere. CareerOS stores the
        summary with delivery state “recorded only” and performs no delivery.
      </Alert>
      <form
        className="grid gap-4 rounded-xl border border-line bg-white p-4 sm:grid-cols-2"
        onSubmit={onSubmit}
      >
        <label className="space-y-2 text-sm font-bold text-foreground">
          Kind
          <Select
            defaultValue="meeting"
            disabled={!contact.consent.allowsOutreach}
            name="kind"
          >
            {interactionKinds.map((item) => (
              <option key={item} value={item}>
                {humanize(item)}
              </option>
            ))}
          </Select>
        </label>
        <label className="space-y-2 text-sm font-bold text-foreground">
          Direction
          <Select
            defaultValue="mutual"
            disabled={!contact.consent.allowsOutreach}
            name="direction"
          >
            {interactionDirections.map((item) => (
              <option key={item} value={item}>
                {humanize(item)}
              </option>
            ))}
          </Select>
        </label>
        <LabeledInput
          disabled={!contact.consent.allowsOutreach}
          id="interaction-time"
          label="When it happened"
          name="occurredAt"
          required
          type="datetime-local"
        />
        <label className="space-y-2 text-sm font-bold text-foreground">
          Reviewed template reference (optional)
          <Select disabled={!contact.consent.allowsOutreach} name="templateId">
            <option value="">No template reference</option>
            {templates.map((template) => (
              <option key={template.id} value={template.id}>
                {template.name}
              </option>
            ))}
          </Select>
          {templateCursor && (
            <Button
              className="min-h-9 px-3"
              onClick={onLoadTemplates}
              type="button"
              variant="ghost"
            >
              Load more templates
            </Button>
          )}
        </label>
        <div className="sm:col-span-2">
          <LabeledTextarea
            disabled={!contact.consent.allowsOutreach}
            id="interaction-summary"
            label="Private summary of what already happened"
            maxLength={4000}
            name="summary"
            required
          />
        </div>
        <Button
          disabled={!contact.consent.allowsOutreach || busy("interaction")}
          type="submit"
        >
          Record local history
        </Button>
      </form>
      <CollectionFilter
        filters={[
          {
            label: "Kind",
            onChange: (value) => setKind(value as InteractionKind | ""),
            options: interactionKinds,
            value: kind,
          },
          {
            label: "Direction",
            onChange: (value) =>
              setDirection(value as InteractionDirection | ""),
            options: interactionDirections,
            value: direction,
          },
        ]}
        onQuery={setQuery}
        query={query}
        searchLabel="Search loaded interactions"
      />
      {visible.length === 0 ? (
        <EmptyState
          description="No loaded interaction records match the current search and filters."
          title="No interaction history matches"
        />
      ) : (
        <ul className="space-y-3">
          {visible.map((interaction) => (
            <li
              className="rounded-xl border border-line bg-white p-4"
              key={interaction.id}
            >
              <div className="flex flex-wrap gap-2">
                <Badge tone="primary">{humanize(interaction.kind)}</Badge>
                <Badge tone="neutral">{humanize(interaction.direction)}</Badge>
                <Badge tone="warning">
                  {humanize(interaction.deliveryState)}
                </Badge>
              </div>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-foreground">
                {interaction.summary}
              </p>
              <p className="mt-2 text-xs text-muted">
                Occurred {dateTime(interaction.occurredAt)}
              </p>
            </li>
          ))}
        </ul>
      )}
      {interactionCursor && (
        <Button
          disabled={busy("more-interactions")}
          onClick={onLoadMore}
          variant="secondary"
        >
          Load more interactions
        </Button>
      )}
    </div>
  );
}

function ReferralsPanel({
  applicationCursor,
  applications,
  busy,
  contact,
  onCreate,
  onLoadApplications,
  onLoadMore,
  onSave,
  referralCursor,
  referrals,
}: {
  applicationCursor: string | null;
  applications: ApplicationSummary[];
  busy: (key: string) => boolean;
  contact: Contact;
  onCreate: (event: FormEvent<HTMLFormElement>) => void;
  onLoadApplications: () => void;
  onLoadMore: () => void;
  onSave: (referral: Referral, event: FormEvent<HTMLFormElement>) => void;
  referralCursor: string | null;
  referrals: Referral[];
}) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<ReferralStatus | "">("");
  const applicationById = useMemo(
    () =>
      new Map(applications.map((application) => [application.id, application])),
    [applications],
  );
  const visible = referrals.filter((referral) => {
    const application = applicationById.get(referral.applicationId);
    return (
      (!status || referral.status === status) &&
      (!query ||
        includesQuery(
          `${referral.context ?? ""} ${referral.status} ${
            application ? applicationLabel(application) : referral.applicationId
          }`,
          query,
        ))
    );
  });
  return (
    <div className="space-y-5 pt-5">
      {!contact.consent.allowsOutreach && (
        <Alert title="Outreach consent required" tone="danger">
          New referral records are blocked until current outreach consent is
          granted.
        </Alert>
      )}
      <Alert title="Local status only" tone="warning">
        Referral records track your plan or an event that happened elsewhere.
        CareerOS never sends a referral request.
      </Alert>
      <form
        className="grid gap-4 rounded-xl border border-line bg-white p-4 sm:grid-cols-2"
        onSubmit={onCreate}
      >
        <label className="space-y-2 text-sm font-bold text-foreground">
          Application
          <Select
            disabled={!contact.consent.allowsOutreach}
            name="applicationId"
            required
          >
            <option value="">Choose an application</option>
            {applications.map((application) => (
              <option key={application.id} value={application.id}>
                {applicationLabel(application)}
              </option>
            ))}
          </Select>
          {applicationCursor && (
            <Button
              className="min-h-9 px-3"
              onClick={onLoadApplications}
              type="button"
              variant="ghost"
            >
              Load more applications
            </Button>
          )}
        </label>
        <label className="space-y-2 text-sm font-bold text-foreground">
          Status
          <Select
            defaultValue="planned"
            disabled={!contact.consent.allowsOutreach}
            name="status"
          >
            {referralStatuses.map((item) => (
              <option key={item} value={item}>
                {humanize(item)}
              </option>
            ))}
          </Select>
        </label>
        <div className="sm:col-span-2">
          <LabeledTextarea
            disabled={!contact.consent.allowsOutreach}
            id="referral-context"
            label="Private context (optional)"
            maxLength={2000}
            name="context"
          />
        </div>
        <Button
          disabled={!contact.consent.allowsOutreach || busy("referral")}
          type="submit"
        >
          Record local referral
        </Button>
      </form>
      <CollectionFilter
        filters={[
          {
            label: "Status",
            onChange: (value) => setStatus(value as ReferralStatus | ""),
            options: referralStatuses,
            value: status,
          },
        ]}
        onQuery={setQuery}
        query={query}
        searchLabel="Search loaded referrals"
      />
      {visible.length === 0 ? (
        <EmptyState
          description="No loaded referral records match the current search and filter."
          title="No referral records match"
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {visible.map((referral) => (
            <form
              className="space-y-3 rounded-xl border border-line bg-white p-4"
              key={`${referral.id}-${referral.version}`}
              onSubmit={(event) => onSave(referral, event)}
            >
              <p className="text-sm font-bold text-foreground">
                {applicationById.has(referral.applicationId)
                  ? applicationLabel(
                      applicationById.get(referral.applicationId)!,
                    )
                  : `Application ${referral.applicationId}`}
              </p>
              <label className="space-y-2 text-sm font-bold text-foreground">
                Status
                <Select defaultValue={referral.status} name="status">
                  {referralStatuses.map((item) => (
                    <option key={item} value={item}>
                      {humanize(item)}
                    </option>
                  ))}
                </Select>
              </label>
              <LabeledTextarea
                defaultValue={referral.context ?? ""}
                id={`referral-${referral.id}-context`}
                label="Private context"
                maxLength={2000}
                name="context"
              />
              <Button disabled={busy(`referral-${referral.id}`)} type="submit">
                Save local state
              </Button>
            </form>
          ))}
        </div>
      )}
      {referralCursor && (
        <Button
          disabled={busy("more-referrals")}
          onClick={onLoadMore}
          variant="secondary"
        >
          Load more referrals
        </Button>
      )}
    </div>
  );
}

function RemindersPanel({
  busy,
  contact,
  executionBusy,
  executions,
  onCreate,
  onLoadMore,
  onResolve,
  onSave,
  reminderCursor,
  reminders,
}: {
  busy: (key: string) => boolean;
  contact: Contact;
  executionBusy: boolean;
  executions: Record<string, LocalReminderExecution | null>;
  onCreate: (event: FormEvent<HTMLFormElement>) => void;
  onLoadMore: () => void;
  onResolve: (reminder: Reminder, input: ReminderResolutionInput) => void;
  onSave: (reminder: Reminder, event: FormEvent<HTMLFormElement>) => void;
  reminderCursor: string | null;
  reminders: Reminder[];
}) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<ReminderStatus | "">("");
  const [queueStatus, setQueueStatus] = useState("");
  const visible = reminders.filter((reminder) => {
    const execution = executions[reminder.id];
    return (
      (!status || reminder.status === status) &&
      (!queueStatus || execution?.queueStatus === queueStatus) &&
      (!query ||
        includesQuery(
          `${reminder.title} ${reminder.status} ${execution?.queueStatus ?? ""} ${
            execution?.lastErrorCode ?? ""
          }`,
          query,
        ))
    );
  });
  return (
    <div className="space-y-5 pt-5">
      {!contact.consent.allowsOutreach && (
        <Alert title="Outreach consent required" tone="danger">
          New reminders are blocked and pending reminders are cancelled when
          outreach consent is absent.
        </Alert>
      )}
      <Alert title="Local workspace reminder — no delivery" tone="warning">
        The durable worker materializes local occurrences and records safe
        processing or failure state. It never emails, messages, pushes, scrapes,
        or fetches contact URLs.
      </Alert>
      <form
        className="grid gap-4 rounded-xl border border-line bg-white p-4 sm:grid-cols-2"
        onSubmit={onCreate}
      >
        <LabeledInput
          disabled={!contact.consent.allowsOutreach}
          id="reminder-title"
          label="Reminder title"
          name="title"
          required
        />
        <LabeledInput
          disabled={!contact.consent.allowsOutreach}
          id="reminder-due"
          label="Due time"
          name="dueAt"
          required
          type="datetime-local"
        />
        <LabeledInput
          disabled={!contact.consent.allowsOutreach}
          id="reminder-recurrence"
          label="Recurrence days (optional)"
          max={365}
          min={1}
          name="recurrenceDays"
          type="number"
        />
        <LabeledInput
          defaultValue="5"
          disabled={!contact.consent.allowsOutreach}
          id="reminder-attempts"
          label="Maximum local processing attempts"
          max={20}
          min={1}
          name="maxAttempts"
          required
          type="number"
        />
        <Button
          disabled={!contact.consent.allowsOutreach || busy("reminder")}
          type="submit"
        >
          Create local reminder
        </Button>
      </form>
      <CollectionFilter
        filters={[
          {
            label: "Reminder status",
            onChange: (value) => setStatus(value as ReminderStatus | ""),
            options: reminderStatuses,
            value: status,
          },
          {
            label: "Execution queue status",
            onChange: setQueueStatus,
            options: [
              "pending",
              "leased",
              "processed",
              "cancelled",
              "dead_letter",
            ],
            value: queueStatus,
          },
        ]}
        onQuery={setQuery}
        query={query}
        searchLabel="Search loaded reminders and safe error codes"
      />
      {visible.length === 0 ? (
        <EmptyState
          description="No loaded local reminders match the current search and filters."
          title="No local reminders match"
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {visible.map((reminder) => (
            <ReminderForm
              busy={
                busy(`reminder-${reminder.id}`) ||
                busy(`reminder-action-${reminder.id}`)
              }
              execution={executions[reminder.id]}
              executionBusy={executionBusy}
              key={`${reminder.id}-${reminder.version}`}
              onResolve={(input) => onResolve(reminder, input)}
              onSubmit={(event) => onSave(reminder, event)}
              reminder={reminder}
            />
          ))}
        </div>
      )}
      {reminderCursor && (
        <Button
          disabled={busy("more-reminders")}
          onClick={onLoadMore}
          variant="secondary"
        >
          Load more reminders
        </Button>
      )}
    </div>
  );
}

function ReminderForm({
  busy,
  execution,
  executionBusy,
  onResolve,
  onSubmit,
  reminder,
}: {
  busy: boolean;
  execution: LocalReminderExecution | null | undefined;
  executionBusy: boolean;
  onResolve: (input: ReminderResolutionInput) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  reminder: Reminder;
}) {
  const [snoozeUntil, setSnoozeUntil] = useState("");
  const due = execution?.occurrenceStatus === "due";
  return (
    <form
      className="space-y-3 rounded-xl border border-line bg-white p-4 shadow-sm"
      onSubmit={onSubmit}
    >
      <LabeledInput
        defaultValue={reminder.title}
        id={`reminder-${reminder.id}-title`}
        label="Title"
        name="title"
        required
      />
      <LabeledInput
        defaultValue={localDateTime(reminder.dueAt)}
        id={`reminder-${reminder.id}-due`}
        label="Due time"
        name="dueAt"
        required
        type="datetime-local"
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <LabeledInput
          defaultValue={reminder.recurrenceDays ?? ""}
          id={`reminder-${reminder.id}-recurrence`}
          label="Recurrence days"
          max={365}
          min={1}
          name="recurrenceDays"
          type="number"
        />
        <label className="space-y-2 text-sm font-bold text-foreground">
          Reminder status
          <Select defaultValue={reminder.status} name="status">
            {reminderStatuses.map((item) => (
              <option key={item} value={item}>
                {humanize(item)}
              </option>
            ))}
          </Select>
        </label>
      </div>
      <ExecutionState
        execution={execution}
        loading={executionBusy}
        reminder={reminder}
      />
      {due && (
        <div className="rounded-lg border border-warning/40 bg-warning/5 p-3">
          <p className="text-sm font-bold text-foreground">
            Waiting for your action
          </p>
          <p className="mt-1 text-xs leading-5 text-muted">
            The worker only made this reminder visible. It remains actionable
            until you acknowledge, complete, or snooze it.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              disabled={busy}
              onClick={() => onResolve({ action: "acknowledge" })}
              type="button"
              variant="secondary"
            >
              Acknowledge
            </Button>
            <Button
              disabled={busy}
              onClick={() => onResolve({ action: "complete" })}
              type="button"
            >
              Complete
            </Button>
          </div>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
            <LabeledInput
              id={`reminder-${reminder.id}-snooze`}
              label="Snooze until"
              onChange={(event) => setSnoozeUntil(event.target.value)}
              type="datetime-local"
            />
            <Button
              disabled={busy || !snoozeUntil}
              onClick={() => {
                if (!snoozeUntil) return;
                onResolve({
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
        </div>
      )}
      <Button disabled={busy} type="submit">
        {busy ? "Saving…" : "Save local reminder"}
      </Button>
    </form>
  );
}

function ExecutionState({
  execution,
  loading,
  reminder,
}: {
  execution: LocalReminderExecution | null | undefined;
  loading: boolean;
  reminder: Reminder;
}) {
  if (execution === undefined) {
    return (
      <div className="rounded-lg border border-line bg-slate-50 p-3 text-sm">
        <p className="flex items-center gap-2 font-bold text-foreground">
          <Clock3 aria-hidden="true" className="size-4" />
          {loading
            ? "Loading local execution state…"
            : "Local execution state unavailable"}
        </p>
        <p className="mt-1 text-xs leading-5 text-muted">
          No external delivery is scheduled.
        </p>
      </div>
    );
  }
  if (execution === null) {
    return (
      <div className="rounded-lg border border-line bg-slate-50 p-3 text-sm">
        <p className="flex items-center gap-2 font-bold text-foreground">
          <Clock3 aria-hidden="true" className="size-4" />
          No local occurrence materialized yet
        </p>
        <p className="mt-1 text-xs leading-5 text-muted">
          The reminder is {humanize(reminder.status)}. No external delivery is
          scheduled.
        </p>
      </div>
    );
  }
  const failed =
    execution.queueStatus === "dead_letter" ||
    execution.occurrenceStatus === "dead_letter";
  return (
    <div
      className={`rounded-lg border p-3 text-sm ${
        failed ? "border-red-200 bg-red-50" : "border-line bg-slate-50"
      }`}
    >
      <div className="flex flex-wrap gap-2">
        <Badge tone={failed ? "danger" : "primary"}>
          Queue: {humanize(execution.queueStatus)}
        </Badge>
        <Badge tone={failed ? "danger" : "neutral"}>
          Occurrence: {humanize(execution.occurrenceStatus)}
        </Badge>
      </div>
      <p className="mt-2 text-xs leading-5 text-muted">
        Local occurrence {execution.occurrenceNumber}, scheduled{" "}
        {dateTime(execution.scheduledFor)}. Attempt {execution.attemptCount} of{" "}
        {execution.maxAttempts}. No delivery action exists.
      </p>
      {execution.lastErrorCode && (
        <p className="mt-2 text-xs font-bold text-danger">
          Safe failure code:{" "}
          <code className="break-all">{execution.lastErrorCode}</code>
        </p>
      )}
    </div>
  );
}

type FilterDefinition = {
  label: string;
  onChange: (value: string) => void;
  options: readonly string[];
  value: string;
};

function CollectionFilter({
  filters = [],
  onQuery,
  query,
  searchLabel,
}: {
  filters?: readonly FilterDefinition[];
  onQuery: (query: string) => void;
  query: string;
  searchLabel: string;
}) {
  return (
    <div
      aria-label="Loaded collection filters"
      className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
      role="search"
    >
      <Input
        aria-label={searchLabel}
        onChange={(event) => onQuery(event.target.value)}
        placeholder={searchLabel}
        value={query}
      />
      {filters.map((filter) => (
        <Select
          aria-label={filter.label}
          key={filter.label}
          onChange={(event) => filter.onChange(event.target.value)}
          value={filter.value}
        >
          <option value="">All {filter.label.toLocaleLowerCase()}</option>
          {filter.options.map((option) => (
            <option key={option} value={option}>
              {humanize(option)}
            </option>
          ))}
        </Select>
      ))}
    </div>
  );
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
        className="min-h-28 w-full rounded-lg border border-line bg-white px-3 py-2 text-sm font-normal text-foreground outline-none transition focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/25 disabled:bg-slate-100 disabled:text-muted"
        id={id}
        {...props}
      />
    </label>
  );
}
