"use client";

import { Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Badge, Button, Input, Select, buttonStyles } from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import { ApiRequestError, updateApplication } from "../api/applications-api";
import type {
  ApplicationDetail,
  OutcomeStatus,
  ReferralStatus,
} from "../api/types";
import {
  formatDateTime,
  humanize,
  outcomeStatuses,
  referralStatuses,
} from "./application-options";
import { ApplicationResumeChangePanel } from "./application-resume-change-panel";

type Contact = ApplicationDetail["contacts"][number];
type EditableContact = Contact & { editorKey: string };

function editableContact(contact?: Contact): EditableContact {
  return {
    email: contact?.email ?? null,
    editorKey: crypto.randomUUID(),
    name: contact?.name ?? "",
    role: contact?.role ?? null,
    url: contact?.url ?? null,
  };
}

export function ApplicationOverviewPanel({
  application,
  onChange,
  onFailure,
  onSuccess,
}: {
  application: ApplicationDetail;
  onChange: (application: ApplicationDetail) => void;
  onFailure: (message: string, conflict: boolean) => void;
  onSuccess: (message: string) => void;
}) {
  const [contacts, setContacts] = useState<EditableContact[]>(() =>
    application.contacts.map((contact) => editableContact(contact)),
  );
  const [busy, setBusy] = useState(false);
  const availableOutcomes =
    application.stage === "rejected"
      ? outcomeStatuses.filter((status) => status === "rejected")
      : application.stage === "withdrawn"
        ? outcomeStatuses.filter((status) => status === "withdrawn")
        : application.stage === "offer"
          ? outcomeStatuses.filter((status) => status !== "none")
          : outcomeStatuses;

  function updateContact(index: number, changes: Partial<Contact>) {
    setContacts((current) =>
      current.map((contact, contactIndex) =>
        contactIndex === index ? { ...contact, ...changes } : contact,
      ),
    );
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const updated = await updateApplication(application, {
        applicationDeadline:
          String(form.get("applicationDeadline") ?? "") || null,
        contacts: contacts.map((contact) => ({
          email: contact.email?.trim() || null,
          name: contact.name.trim(),
          role: contact.role?.trim() || null,
          url: contact.url?.trim() || null,
        })),
        followUpAt: String(form.get("followUpAt") ?? "") || null,
        industry: String(form.get("industry") ?? "").trim() || null,
        offerSummary: String(form.get("offerSummary") ?? "").trim() || null,
        outcomeStatus: String(form.get("outcomeStatus")) as OutcomeStatus,
        referralStatus: String(form.get("referralStatus")) as ReferralStatus,
        rejectionReason:
          String(form.get("rejectionReason") ?? "").trim() || null,
        source: String(form.get("source") ?? "").trim() || null,
      });
      onChange(updated);
      onSuccess("Application details saved.");
    } catch (error) {
      const conflict =
        error instanceof ApiRequestError &&
        (error.failure.status === 409 || error.failure.status === 412);
      onFailure(
        conflict
          ? "This application changed in another session. Reload before saving."
          : requestErrorMessage(
              error,
              "Application details could not be saved.",
            ),
        conflict,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
      <form
        className="rounded-xl border border-line bg-white p-4 shadow-sm sm:p-5"
        onSubmit={(event) => void save(event)}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-black text-foreground">
            Workflow details
          </h2>
          <Badge tone="neutral">Version {application.version}</Badge>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="text-sm font-bold text-foreground">
            Application deadline
            <Input
              className="mt-1"
              defaultValue={application.applicationDeadline ?? ""}
              name="applicationDeadline"
              type="date"
            />
          </label>
          <label className="text-sm font-bold text-foreground">
            Follow-up date
            <Input
              className="mt-1"
              defaultValue={application.followUpAt ?? ""}
              name="followUpAt"
              type="date"
            />
          </label>
          <label className="text-sm font-bold text-foreground">
            Application source
            <Input
              className="mt-1"
              defaultValue={application.source ?? ""}
              maxLength={120}
              name="source"
              placeholder="For example, referral or company site"
            />
          </label>
          <label className="text-sm font-bold text-foreground">
            Industry
            <Input
              className="mt-1"
              defaultValue={application.industry ?? ""}
              maxLength={120}
              name="industry"
            />
          </label>
          <label className="text-sm font-bold text-foreground">
            Referral status
            <Select
              className="mt-1"
              defaultValue={application.referralStatus}
              name="referralStatus"
            >
              {referralStatuses.map((status) => (
                <option key={status} value={status}>
                  {humanize(status)}
                </option>
              ))}
            </Select>
          </label>
          <label className="text-sm font-bold text-foreground">
            Outcome
            <Select
              className="mt-1"
              defaultValue={application.outcomeStatus}
              name="outcomeStatus"
            >
              {availableOutcomes.map((status) => (
                <option key={status} value={status}>
                  {humanize(status)}
                </option>
              ))}
            </Select>
            <span className="mt-1 block text-xs font-normal text-muted">
              Recording an offer, rejection, or withdrawal also updates the
              workflow stage.
            </span>
          </label>
          <label className="text-sm font-bold text-foreground md:col-span-2">
            Rejection reason
            <textarea
              className="mt-1 min-h-24 w-full resize-y rounded-xl border border-line bg-white px-3.5 py-3 text-sm text-foreground shadow-sm outline-none focus:border-primary focus:ring-3 focus:ring-primary-soft"
              defaultValue={application.rejectionReason ?? ""}
              maxLength={500}
              name="rejectionReason"
            />
          </label>
          <label className="text-sm font-bold text-foreground md:col-span-2">
            Offer information
            <textarea
              className="mt-1 min-h-24 w-full resize-y rounded-xl border border-line bg-white px-3.5 py-3 text-sm text-foreground shadow-sm outline-none focus:border-primary focus:ring-3 focus:ring-primary-soft"
              defaultValue={application.offerSummary ?? ""}
              maxLength={500}
              name="offerSummary"
            />
          </label>
        </div>

        <fieldset className="mt-6 border-t border-line pt-5">
          <legend className="text-base font-black text-foreground">
            Contacts
          </legend>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted">
              Recruiters, hiring managers, and referral contacts
            </p>
            <Button
              className="min-h-9 px-3"
              disabled={contacts.length >= 20}
              onClick={() =>
                setContacts((current) => [...current, editableContact()])
              }
              variant="secondary"
            >
              <Plus aria-hidden="true" className="size-4" />
              Add contact
            </Button>
          </div>
          {contacts.length ? (
            <div className="mt-4 space-y-4">
              {contacts.map((contact, index) => (
                <fieldset
                  className="rounded-xl bg-slate-50 p-3"
                  key={contact.editorKey}
                >
                  <legend className="px-1 text-sm font-black text-foreground">
                    Contact {index + 1}
                    {contact.name ? `: ${contact.name}` : ""}
                  </legend>
                  <div className="grid gap-3 md:grid-cols-2">
                    <label className="text-sm font-bold text-foreground">
                      Name
                      <Input
                        className="mt-1"
                        maxLength={120}
                        onChange={(event) =>
                          updateContact(index, { name: event.target.value })
                        }
                        required
                        value={contact.name}
                      />
                    </label>
                    <label className="text-sm font-bold text-foreground">
                      Role
                      <Input
                        className="mt-1"
                        maxLength={120}
                        onChange={(event) =>
                          updateContact(index, {
                            role: event.target.value || null,
                          })
                        }
                        value={contact.role ?? ""}
                      />
                    </label>
                    <label className="text-sm font-bold text-foreground">
                      Email
                      <Input
                        className="mt-1"
                        maxLength={254}
                        onChange={(event) =>
                          updateContact(index, {
                            email: event.target.value || null,
                          })
                        }
                        type="email"
                        value={contact.email ?? ""}
                      />
                    </label>
                    <label className="text-sm font-bold text-foreground">
                      Profile or contact URL
                      <Input
                        className="mt-1"
                        maxLength={500}
                        onChange={(event) =>
                          updateContact(index, {
                            url: event.target.value || null,
                          })
                        }
                        type="url"
                        value={contact.url ?? ""}
                      />
                    </label>
                    <div className="md:col-span-2">
                      <Button
                        aria-label={`Remove contact ${contact.name || index + 1}`}
                        className="min-h-9 px-3"
                        onClick={() =>
                          setContacts((current) =>
                            current.filter(
                              (_, contactIndex) => contactIndex !== index,
                            ),
                          )
                        }
                        variant="ghost"
                      >
                        <Trash2 aria-hidden="true" className="size-4" />
                        Remove contact
                      </Button>
                    </div>
                  </div>
                </fieldset>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm text-muted">
              No recruiter, hiring manager, or referral contacts recorded.
            </p>
          )}
        </fieldset>

        <Button className="mt-6" loading={busy} type="submit">
          Save workflow details
        </Button>
      </form>

      <aside className="space-y-4">
        <section className="rounded-xl border border-line bg-white p-4 shadow-sm">
          <h2 className="text-base font-black text-foreground">
            Pinned sources
          </h2>
          <dl className="mt-3 space-y-3 text-sm">
            <div>
              <dt className="font-bold text-muted">Saved job</dt>
              <dd className="text-foreground">
                Version {application.jobVersion}
              </dd>
            </div>
            <div>
              <dt className="font-bold text-muted">Resume</dt>
              <dd className="text-foreground">{application.resumeTitle}</dd>
              <dd className="text-xs text-muted">
                Immutable version {application.resumeVersionNumber}
              </dd>
            </div>
            <div>
              <dt className="font-bold text-muted">Evidence pins</dt>
              <dd className="text-foreground">
                {application.evidencePins.length} exact revisions
              </dd>
            </div>
            <div>
              <dt className="font-bold text-muted">Job requirements</dt>
              <dd className="text-foreground">
                {application.jobRequirements.length} pinned requirements
              </dd>
            </div>
            <div>
              <dt className="font-bold text-muted">Job source fingerprint</dt>
              <dd
                className="truncate font-mono text-xs text-foreground"
                title={application.jobSourceSha256}
              >
                {application.jobSourceSha256}
              </dd>
            </div>
            <div>
              <dt className="font-bold text-muted">Last updated</dt>
              <dd className="text-foreground">
                {formatDateTime(application.updatedAt)}
              </dd>
            </div>
          </dl>
          <div className="mt-4 flex flex-col gap-2">
            <Link
              className={buttonStyles.secondary + " " + buttonStyles.base}
              href="/job-match"
            >
              Open saved jobs
            </Link>
            <Link
              className={buttonStyles.ghost + " " + buttonStyles.base}
              href="/resume-builder"
            >
              Open resume builder
            </Link>
          </div>
        </section>
        <ApplicationResumeChangePanel
          application={application}
          onChange={onChange}
          onFailure={onFailure}
          onSuccess={onSuccess}
        />
        <section className="rounded-xl border border-line bg-white p-4 shadow-sm">
          <h2 className="text-base font-black text-foreground">
            Grounding snapshot
          </h2>
          {application.evidencePins.length ? (
            <ul className="mt-3 space-y-3">
              {application.evidencePins.slice(0, 5).map((pin) => (
                <li
                  className="rounded-lg bg-slate-50 p-3"
                  key={pin.evidenceRevisionId}
                >
                  <p className="line-clamp-3 text-sm text-foreground">
                    {pin.statement}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    {humanize(pin.strength)} · Revision {pin.revisionNumber}
                    {pin.hasNumericClaim ? " · Numeric claim confirmed" : ""}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted">
              This resume version has no eligible evidence pins.
            </p>
          )}
          {application.evidencePins.length > 5 && (
            <p className="mt-3 text-xs text-muted">
              {application.evidencePins.length - 5} more pinned revisions are
              available to the consistency engine.
            </p>
          )}
        </section>
      </aside>
    </div>
  );
}
