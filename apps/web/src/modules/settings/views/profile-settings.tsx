"use client";

import { RefreshCcw } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  ErrorState,
  FieldLabel,
  LoadingSkeleton,
  Select,
  TextField,
} from "@careeros/ui";

import {
  ApiRequestError,
  requestErrorMessage,
} from "@/shared/api/browser-request";

import {
  getProfile,
  type ProfileState,
  updateProfile,
} from "../api/settings-api";

export function ProfileSettings() {
  const [profile, setProfile] = useState<ProfileState>();
  const [failure, setFailure] = useState<string>();
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const saved = await getProfile();
      setFailure(undefined);
      setProfile(saved);
    } catch (error) {
      setFailure(requestErrorMessage(error, "We couldn’t load your profile."));
    }
  }, []);
  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile) return;
    const form = new FormData(event.currentTarget);
    const optional = (name: string) =>
      String(form.get(name) ?? "").trim() || null;
    const displayName = String(form.get("displayName") ?? "").trim();
    if (!displayName) {
      setFailure("Enter the name you want CareerOS to use.");
      return;
    }
    setSaving(true);
    setFailure(undefined);
    setSaved(false);
    try {
      setProfile(
        await updateProfile(profile, {
          displayName,
          industry: optional("industry"),
          language: String(form.get("language") ?? "").trim(),
          locale: String(form.get("locale") ?? "").trim(),
          preferredLocation: optional("preferredLocation"),
          seniority: optional("seniority") as ProfileState["seniority"],
          targetRole: optional("targetRole"),
          timezone: String(form.get("timezone") ?? "").trim(),
          workModel: optional("workModel") as ProfileState["workModel"],
          writingStyle: String(
            form.get("writingStyle"),
          ) as ProfileState["writingStyle"],
        }),
      );
      setSaved(true);
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "Your profile changed in another tab. Reload before saving again."
          : requestErrorMessage(error, "We couldn’t save your profile."),
      );
    } finally {
      setSaving(false);
    }
  }

  if (!profile && !failure) return <LoadingSkeleton variant="form" />;
  if (!profile)
    return (
      <ErrorState
        description={failure ?? "We couldn’t load your profile."}
        onRetry={load}
        title="Profile unavailable"
      />
    );

  return (
    <Card className="p-5 sm:p-7">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-extrabold text-foreground">
            Profile and account
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted">
            Manage presentation and future filtering preferences. Employment
            facts are not stored here.
          </p>
        </div>
        <Badge tone={profile.emailVerified ? "success" : "warning"}>
          {profile.emailVerified ? "Email verified" : "Verification required"}
        </Badge>
      </div>
      {failure && (
        <Alert className="mb-5" title="Profile not saved" tone="danger">
          {failure}
          <Button className="mt-3" onClick={load} variant="secondary">
            <RefreshCcw aria-hidden="true" className="size-4" /> Reload profile
          </Button>
        </Alert>
      )}
      {saved && (
        <Alert className="mb-5" title="Profile saved" tone="success">
          Your current account preferences are up to date.
        </Alert>
      )}
      <form className="space-y-5" onSubmit={onSubmit}>
        <div className="grid gap-5 sm:grid-cols-2">
          <TextField
            defaultValue={profile.displayName}
            id="displayName"
            label="Name"
            maxLength={100}
            name="displayName"
            required
          />
          <TextField
            disabled
            id="accountEmail"
            label="Verified email"
            value={profile.email}
          />
          <TextField
            defaultValue={profile.targetRole ?? ""}
            id="targetRole"
            label="Target role (optional)"
            maxLength={160}
            name="targetRole"
          />
          <TextField
            defaultValue={profile.preferredLocation ?? ""}
            id="preferredLocation"
            label="Preferred location (optional)"
            maxLength={160}
            name="preferredLocation"
          />
          <div className="space-y-2">
            <FieldLabel htmlFor="workModel">Work model (optional)</FieldLabel>
            <Select
              defaultValue={profile.workModel ?? ""}
              id="workModel"
              name="workModel"
            >
              <option value="">No preference</option>
              <option value="onsite">On-site</option>
              <option value="hybrid">Hybrid</option>
              <option value="remote">Remote</option>
              <option value="flexible">Flexible</option>
            </Select>
          </div>
          <div className="space-y-2">
            <FieldLabel htmlFor="seniority">Seniority (optional)</FieldLabel>
            <Select
              defaultValue={profile.seniority ?? ""}
              id="seniority"
              name="seniority"
            >
              <option value="">No preference</option>
              <option value="entry">Entry</option>
              <option value="mid">Mid-level</option>
              <option value="senior">Senior</option>
              <option value="lead">Lead</option>
              <option value="executive">Executive</option>
            </Select>
          </div>
          <TextField
            defaultValue={profile.industry ?? ""}
            id="industry"
            label="Industry (optional)"
            maxLength={120}
            name="industry"
          />
          <TextField
            defaultValue={profile.language}
            id="language"
            label="Language"
            maxLength={35}
            name="language"
            required
          />
          <TextField
            defaultValue={profile.locale}
            id="locale"
            label="Locale"
            maxLength={35}
            name="locale"
            required
          />
          <TextField
            defaultValue={profile.timezone}
            id="timezone"
            label="Time zone"
            maxLength={64}
            name="timezone"
            required
          />
          <div className="space-y-2 sm:col-span-2">
            <FieldLabel htmlFor="writingStyle">Writing preference</FieldLabel>
            <Select
              defaultValue={profile.writingStyle}
              id="writingStyle"
              name="writingStyle"
            >
              <option value="concise">Concise</option>
              <option value="balanced">Balanced</option>
              <option value="detailed">Detailed</option>
            </Select>
          </div>
        </div>
        <div className="flex justify-end">
          <Button loading={saving} loadingLabel="Saving profile…" type="submit">
            Save profile
          </Button>
        </div>
      </form>
    </Card>
  );
}
