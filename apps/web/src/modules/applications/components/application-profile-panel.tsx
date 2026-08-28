"use client";

import { Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { Alert, Button, Input } from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  getApplicationProfile,
  upsertApplicationProfile,
} from "../api/applications-api";
import type { ApplicationProfileLink } from "../api/types";

type DisclosureRow = { key: string; value: string };

/**
 * Answers filled in once and reused by the assisted-apply handoff pack
 * (`ApplicationPacksPanel`'s "Ready to submit" card). Voluntary disclosures
 * (e.g. disability self-identification) are the owner's own opt-in entries —
 * Meridian never infers or auto-populates them.
 */
export function ApplicationProfilePanel() {
  const [loaded, setLoaded] = useState(false);
  const [workAuthorization, setWorkAuthorization] = useState("");
  const [noticePeriodDays, setNoticePeriodDays] = useState("");
  const [compensationMin, setCompensationMin] = useState("");
  const [compensationMax, setCompensationMax] = useState("");
  const [compensationCurrency, setCompensationCurrency] = useState("USD");
  const [preferredLocations, setPreferredLocations] = useState("");
  const [profileLinks, setProfileLinks] = useState<ApplicationProfileLink[]>(
    [],
  );
  const [disclosures, setDisclosures] = useState<DisclosureRow[]>([]);
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setFailure(undefined);
    try {
      const profile = await getApplicationProfile();
      if (profile) {
        setWorkAuthorization(profile.workAuthorization ?? "");
        setNoticePeriodDays(
          profile.noticePeriodDays === null || profile.noticePeriodDays === undefined
            ? ""
            : String(profile.noticePeriodDays),
        );
        setCompensationMin(
          profile.compensationMin === null || profile.compensationMin === undefined
            ? ""
            : String(profile.compensationMin),
        );
        setCompensationMax(
          profile.compensationMax === null || profile.compensationMax === undefined
            ? ""
            : String(profile.compensationMax),
        );
        setCompensationCurrency(profile.compensationCurrency);
        setPreferredLocations((profile.preferredLocations ?? []).join(", "));
        setProfileLinks(profile.profileLinks ?? []);
        setDisclosures(
          Object.entries(profile.voluntaryDisclosures ?? {}).map(
            ([key, value]) => ({ key, value }),
          ),
        );
      }
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "Your Application Profile could not be loaded."),
      );
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  function addLink() {
    setProfileLinks((current) => [...current, { label: "", url: "" }]);
  }

  function updateLink(index: number, next: Partial<ApplicationProfileLink>) {
    setProfileLinks((current) =>
      current.map((link, itemIndex) =>
        itemIndex === index ? { ...link, ...next } : link,
      ),
    );
  }

  function removeLink(index: number) {
    setProfileLinks((current) => current.filter((_, i) => i !== index));
  }

  function addDisclosure() {
    setDisclosures((current) => [...current, { key: "", value: "" }]);
  }

  function updateDisclosure(index: number, next: Partial<DisclosureRow>) {
    setDisclosures((current) =>
      current.map((row, itemIndex) =>
        itemIndex === index ? { ...row, ...next } : row,
      ),
    );
  }

  function removeDisclosure(index: number) {
    setDisclosures((current) => current.filter((_, i) => i !== index));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const voluntaryDisclosures = Object.fromEntries(
        disclosures
          .map(({ key, value }) => [key.trim(), value.trim()] as const)
          .filter(([key, value]) => key && value),
      );
      const links = profileLinks
        .map((link) => ({ label: link.label.trim(), url: link.url.trim() }))
        .filter((link) => link.label && link.url);
      await upsertApplicationProfile({
        compensationCurrency: compensationCurrency.trim().toUpperCase() || "USD",
        compensationMax: compensationMax ? Number(compensationMax) : null,
        compensationMin: compensationMin ? Number(compensationMin) : null,
        noticePeriodDays: noticePeriodDays ? Number(noticePeriodDays) : null,
        preferredLocations: preferredLocations
          .split(",")
          .map((location) => location.trim())
          .filter(Boolean),
        profileLinks: links,
        voluntaryDisclosures,
        workAuthorization: workAuthorization.trim() || null,
      });
      setSuccess("Application Profile saved. It will be used the next time you apply for me.");
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "Your Application Profile could not be saved."),
      );
    } finally {
      setSaving(false);
    }
  }

  if (!loaded) {
    return <p className="text-sm text-muted">Loading your Application Profile…</p>;
  }

  return (
    <form className="space-y-5" onSubmit={(event) => void save(event)}>
      <p className="text-sm text-muted">
        Fill this in once. It answers the questions most job applications ask,
        so &ldquo;Apply for me&rdquo; on Job search can assemble a
        ready-to-submit pack — you still open it and submit it yourself.
      </p>

      {failure && (
        <Alert title="Application Profile not saved" tone="danger">
          {failure}
        </Alert>
      )}
      {success && (
        <Alert title="Saved" tone="success">
          {success}
        </Alert>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm font-bold text-foreground">
          Work authorization
          <Input
            maxLength={500}
            onChange={(event) => setWorkAuthorization(event.target.value)}
            placeholder="e.g. Authorized to work in the US, no sponsorship needed"
            value={workAuthorization}
          />
        </label>
        <label className="text-sm font-bold text-foreground">
          Notice period (days)
          <Input
            max={730}
            min={0}
            onChange={(event) => setNoticePeriodDays(event.target.value)}
            type="number"
            value={noticePeriodDays}
          />
        </label>
        <label className="text-sm font-bold text-foreground">
          Minimum compensation
          <Input
            min={0}
            onChange={(event) => setCompensationMin(event.target.value)}
            type="number"
            value={compensationMin}
          />
        </label>
        <label className="text-sm font-bold text-foreground">
          Maximum compensation
          <Input
            min={0}
            onChange={(event) => setCompensationMax(event.target.value)}
            type="number"
            value={compensationMax}
          />
        </label>
        <label className="text-sm font-bold text-foreground">
          Compensation currency
          <Input
            maxLength={3}
            minLength={3}
            onChange={(event) => setCompensationCurrency(event.target.value)}
            value={compensationCurrency}
          />
        </label>
        <label className="text-sm font-bold text-foreground sm:col-span-2">
          Preferred locations (comma-separated)
          <Input
            onChange={(event) => setPreferredLocations(event.target.value)}
            placeholder="Remote, New York NY, Austin TX"
            value={preferredLocations}
          />
        </label>
      </div>

      <div>
        <div className="flex items-center justify-between">
          <p className="text-sm font-bold text-foreground">Profile links</p>
          <Button onClick={addLink} type="button" variant="secondary">
            <Plus aria-hidden="true" className="size-4" />
            Add link
          </Button>
        </div>
        <div className="mt-2 space-y-2">
          {profileLinks.map((link, index) => (
            <div className="flex gap-2" key={index}>
              <Input
                aria-label="Link label"
                onChange={(event) =>
                  updateLink(index, { label: event.target.value })
                }
                placeholder="Label, e.g. Portfolio"
                value={link.label}
              />
              <Input
                aria-label="Link URL"
                onChange={(event) =>
                  updateLink(index, { url: event.target.value })
                }
                placeholder="https://…"
                value={link.url}
              />
              <Button
                aria-label={`Remove link ${index + 1}`}
                onClick={() => removeLink(index)}
                type="button"
                variant="ghost"
              >
                <Trash2 aria-hidden="true" className="size-4" />
              </Button>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between">
          <p className="text-sm font-bold text-foreground">
            Voluntary disclosures
          </p>
          <Button onClick={addDisclosure} type="button" variant="secondary">
            <Plus aria-hidden="true" className="size-4" />
            Add disclosure
          </Button>
        </div>
        <p className="mt-1 text-xs text-muted">
          Optional. Some applications ask about disability status, veteran
          status, or similar — add only what you choose to disclose yourself;
          Meridian never fills these in for you.
        </p>
        <div className="mt-2 space-y-2">
          {disclosures.map((row, index) => (
            <div className="flex gap-2" key={index}>
              <Input
                aria-label="Disclosure question"
                onChange={(event) =>
                  updateDisclosure(index, { key: event.target.value })
                }
                placeholder="e.g. disability_status"
                value={row.key}
              />
              <Input
                aria-label="Disclosure answer"
                onChange={(event) =>
                  updateDisclosure(index, { value: event.target.value })
                }
                placeholder="Your answer"
                value={row.value}
              />
              <Button
                aria-label={`Remove disclosure ${index + 1}`}
                onClick={() => removeDisclosure(index)}
                type="button"
                variant="ghost"
              >
                <Trash2 aria-hidden="true" className="size-4" />
              </Button>
            </div>
          ))}
        </div>
      </div>

      <Button loading={saving} type="submit">
        Save Application Profile
      </Button>
    </form>
  );
}
