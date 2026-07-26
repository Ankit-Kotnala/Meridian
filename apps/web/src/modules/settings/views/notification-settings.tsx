"use client";

import { BellRing, RefreshCcw } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  Card,
  CheckboxField,
  ErrorState,
  LoadingSkeleton,
  TextField,
} from "@careeros/ui";

import {
  ApiRequestError,
  requestErrorMessage,
} from "@/shared/api/browser-request";

import {
  getReminderPreferences,
  getSettingsCapabilities,
  updateReminderPreferences,
  type ReminderPreferences,
  type SettingsCapabilities,
} from "../api/settings-api";

export function NotificationSettings() {
  const [preferences, setPreferences] = useState<ReminderPreferences>();
  const [capabilities, setCapabilities] = useState<SettingsCapabilities>();
  const [failure, setFailure] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [nextPreferences, nextCapabilities] = await Promise.all([
        getReminderPreferences(),
        getSettingsCapabilities(),
      ]);
      setPreferences(nextPreferences);
      setCapabilities(nextCapabilities);
      setFailure(undefined);
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "We couldn’t load notification preferences.",
        ),
      );
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!preferences) return;
    const form = new FormData(event.currentTarget);
    const enabled = form.get("enabled") === "on";
    const day = Number(form.get("dayOfMonth"));
    if (enabled && (!Number.isInteger(day) || day < 1 || day > 28)) {
      setFailure("Choose a reminder day from 1 through 28.");
      return;
    }
    const timezone = String(form.get("timezone") ?? "").trim();
    if (!timezone) {
      setFailure("Enter an IANA time zone.");
      return;
    }
    setSaving(true);
    setFailure(undefined);
    setNotice(undefined);
    try {
      setPreferences(
        await updateReminderPreferences(preferences, {
          enabled,
          dayOfMonth: enabled ? day : null,
          timezone,
        }),
      );
      setNotice("Reminder preferences saved.");
    } catch (error) {
      setFailure(
        error instanceof ApiRequestError && error.failure.status === 409
          ? "These preferences changed elsewhere. Reload before saving."
          : requestErrorMessage(
              error,
              "We couldn’t save notification preferences.",
            ),
      );
    } finally {
      setSaving(false);
    }
  }

  if (!preferences && !failure) return <LoadingSkeleton variant="form" />;
  if (!preferences || !capabilities)
    return (
      <ErrorState
        description={failure ?? "We couldn’t load notification preferences."}
        onRetry={load}
        title="Notification settings unavailable"
      />
    );

  return (
    <Card className="p-5 sm:p-7">
      <div className="flex items-start gap-3 border-b border-line pb-5">
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
          <BellRing aria-hidden="true" className="size-5" />
        </span>
        <div>
          <h2 className="text-lg font-extrabold text-foreground">
            Achievement capture reminders
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
            Save a monthly schedule preference for capturing new evidence.
            Security and transactional account messages are not controlled by
            this preference.
          </p>
        </div>
      </div>

      {!capabilities.scheduledNotificationDeliveryAvailable && (
        <Alert
          className="mt-5"
          title="Scheduled delivery is not configured"
          tone="warning"
        >
          The schedule is stored, but this environment does not send reminder
          email or push notifications. No delivery is implied until a configured
          durable notification worker is available.
        </Alert>
      )}
      {failure && (
        <Alert className="mt-5" title="Preferences not saved" tone="danger">
          {failure}
          <Button
            className="mt-3"
            onClick={() => void load()}
            variant="secondary"
          >
            <RefreshCcw aria-hidden="true" className="size-4" /> Reload
          </Button>
        </Alert>
      )}
      {notice && <Alert className="mt-5" title={notice} tone="success" />}

      <form className="mt-5 space-y-5" onSubmit={onSubmit}>
        <CheckboxField
          defaultChecked={preferences.enabled}
          description="This records your schedule choice; delivery availability is reported above."
          id="reminders-enabled"
          label="Enable monthly capture reminders"
          name="enabled"
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            defaultValue={preferences.dayOfMonth ?? 1}
            id="reminder-day"
            label="Day of month"
            max={28}
            min={1}
            name="dayOfMonth"
            type="number"
          />
          <TextField
            defaultValue={preferences.timezone}
            hint="For example: Asia/Kolkata or America/New_York."
            id="reminder-timezone"
            label="IANA time zone"
            maxLength={64}
            name="timezone"
            required
          />
        </div>
        <div className="flex justify-end">
          <Button
            loading={saving}
            loadingLabel="Saving preferences…"
            type="submit"
          >
            Save reminder preferences
          </Button>
        </div>
      </form>
    </Card>
  );
}
