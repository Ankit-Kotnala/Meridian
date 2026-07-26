"use client";

import { KeyRound, RefreshCcw, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  TextField,
} from "@careeros/ui";

import {
  ApiRequestError,
  requestErrorMessage,
} from "@/shared/api/browser-request";

import {
  changePassword,
  getSecurityActivity,
  getSettingsCapabilities,
  type SecurityActivity,
  type SettingsCapabilities,
} from "../api/settings-api";

function dateTime(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf())
    ? "Unknown time"
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(parsed);
}

function activityLabel(value: string): string {
  const labels: Record<string, string> = {
    "account.consent_recorded": "Consent choice recorded",
    "account.profile_updated": "Profile settings updated",
    "auth.google_disconnected": "Google connection removed",
    "auth.login": "Account sign-in",
    "auth.logout": "Account sign-out",
    "auth.logout_all": "All sessions signed out",
    "auth.password_change": "Password changed",
    "auth.password_reset": "Password reset",
    "auth.refresh_reuse": "Reused refresh credential blocked",
    "auth.session_revoked": "Session revoked",
  };
  return labels[value] ?? "Account security activity";
}

export function SecuritySettings() {
  const router = useRouter();
  const [capabilities, setCapabilities] = useState<SettingsCapabilities>();
  const [activity, setActivity] = useState<SecurityActivity[]>();
  const [failure, setFailure] = useState<string>();
  const [passwordFailure, setPasswordFailure] = useState<string>();
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [nextCapabilities, nextActivity] = await Promise.all([
        getSettingsCapabilities(),
        getSecurityActivity(),
      ]);
      setCapabilities(nextCapabilities);
      setActivity(nextActivity);
      setFailure(undefined);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t load account security."),
      );
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  async function onPasswordSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!capabilities) return;
    const form = new FormData(event.currentTarget);
    const currentPassword = String(form.get("currentPassword") ?? "");
    const newPassword = String(form.get("newPassword") ?? "");
    const confirmation = String(form.get("confirmation") ?? "");
    if (newPassword.length < 12 || newPassword.length > 128) {
      setPasswordFailure("Use a password from 12 to 128 characters.");
      return;
    }
    if (newPassword !== confirmation) {
      setPasswordFailure("The new passwords do not match.");
      return;
    }
    setSaving(true);
    setPasswordFailure(undefined);
    try {
      await changePassword(
        capabilities.hasPassword ? currentPassword : null,
        newPassword,
      );
      router.replace("/login?passwordChanged=1");
      router.refresh();
    } catch (error) {
      setPasswordFailure(
        error instanceof ApiRequestError &&
          error.failure.code === "recent_authentication_required"
          ? "Sign out and sign in again before changing your password."
          : requestErrorMessage(error, "We couldn’t change your password."),
      );
    } finally {
      setSaving(false);
    }
  }

  if (!capabilities && !failure) return <LoadingSkeleton variant="form" />;
  if (!capabilities || !activity)
    return (
      <ErrorState
        description={failure ?? "We couldn’t load account security."}
        onRetry={load}
        title="Account security unavailable"
      />
    );

  return (
    <div className="space-y-5">
      <Card className="p-5 sm:p-7">
        <div className="flex items-start gap-3 border-b border-line pb-5">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
            <KeyRound aria-hidden="true" className="size-5" />
          </span>
          <div>
            <h2 className="text-lg font-extrabold text-foreground">
              {capabilities.hasPassword ? "Change password" : "Set a password"}
            </h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
              This sensitive action requires a recent sign-in. Success revokes
              every active session, including this one.
            </p>
          </div>
        </div>
        {passwordFailure && (
          <Alert className="mt-5" title="Password not changed" tone="danger">
            {passwordFailure}
          </Alert>
        )}
        <form className="mt-5 space-y-4" onSubmit={onPasswordSubmit}>
          {capabilities.hasPassword && (
            <TextField
              autoComplete="current-password"
              id="currentPassword"
              label="Current password"
              maxLength={128}
              name="currentPassword"
              required
              type="password"
            />
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              autoComplete="new-password"
              hint="Use 12–128 characters. A password manager is recommended."
              id="newPassword"
              label="New password"
              maxLength={128}
              minLength={12}
              name="newPassword"
              required
              type="password"
            />
            <TextField
              autoComplete="new-password"
              id="confirmation"
              label="Confirm new password"
              maxLength={128}
              minLength={12}
              name="confirmation"
              required
              type="password"
            />
          </div>
          <div className="flex justify-end">
            <Button
              loading={saving}
              loadingLabel="Updating password…"
              type="submit"
            >
              {capabilities.hasPassword ? "Change password" : "Set password"}
            </Button>
          </div>
        </form>
      </Card>

      <Card className="p-5 sm:p-7">
        <div className="flex flex-col gap-3 border-b border-line pb-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-success-soft text-success">
              <ShieldCheck aria-hidden="true" className="size-5" />
            </span>
            <div>
              <h2 className="text-lg font-extrabold text-foreground">
                Security activity
              </h2>
              <p className="mt-1 text-sm leading-6 text-muted">
                Recent redacted account events. Passwords, tokens, document
                content, and raw network addresses are never shown.
              </p>
            </div>
          </div>
          <Button onClick={() => void load()} variant="secondary">
            <RefreshCcw aria-hidden="true" className="size-4" /> Refresh
          </Button>
        </div>
        {failure && (
          <Alert className="mt-5" title="Activity not refreshed" tone="danger">
            {failure}
          </Alert>
        )}
        {activity.length === 0 ? (
          <EmptyState
            className="mt-5"
            description="No account security events were returned."
            title="No recent activity"
          />
        ) : (
          <ul className="mt-2 divide-y divide-line">
            {activity.map((item) => (
              <li
                className="flex flex-wrap items-center justify-between gap-3 py-4"
                key={item.id}
              >
                <div>
                  <p className="text-sm font-extrabold text-foreground">
                    {activityLabel(item.eventType)}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    {dateTime(item.occurredAt)}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {item.currentSession && (
                    <Badge tone="primary">Current session</Badge>
                  )}
                  <Badge
                    tone={item.outcome === "denied" ? "warning" : "success"}
                  >
                    {item.outcome}
                  </Badge>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
