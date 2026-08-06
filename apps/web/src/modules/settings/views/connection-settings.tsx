"use client";

import { Link2, RefreshCcw, Unlink } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  ErrorState,
  LoadingSkeleton,
  buttonStyles,
  cn,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  disconnectGoogle,
  getSettingsCapabilities,
  type SettingsCapabilities,
} from "../api/settings-api";

export function ConnectionSettings() {
  const [capabilities, setCapabilities] = useState<SettingsCapabilities>();
  const [failure, setFailure] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setCapabilities(await getSettingsCapabilities());
      setFailure(undefined);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t load account connections."),
      );
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  async function disconnect() {
    setBusy(true);
    setFailure(undefined);
    setNotice(undefined);
    try {
      await disconnectGoogle();
      setCapabilities((current) =>
        current ? { ...current, googleConnected: false } : current,
      );
      setNotice("Google was disconnected from this account.");
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "We couldn’t disconnect Google. A password sign-in method and a recent sign-in are required.",
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  if (!capabilities && !failure) return <LoadingSkeleton variant="form" />;
  if (!capabilities)
    return (
      <ErrorState
        description={failure ?? "We couldn’t load account connections."}
        onRetry={load}
        title="Connections unavailable"
      />
    );

  return (
    <Card className="p-5 sm:p-7">
      <div className="flex items-start gap-3 border-b border-line pb-5">
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
          <Link2 aria-hidden="true" className="size-5" />
        </span>
        <div>
          <h2 className="text-lg font-extrabold text-foreground">
            Connected sign-in methods
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
            Connections shown here come from server configuration and your
            account’s persisted OAuth state.
          </p>
        </div>
      </div>
      {failure && (
        <Alert className="mt-5" title="Connection action failed" tone="danger">
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
      <div className="mt-5 flex flex-col gap-4 rounded-[var(--radius-card)] border border-line p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-extrabold text-foreground">Google</p>
            <Badge tone={capabilities.googleConnected ? "success" : "neutral"}>
              {capabilities.googleConnected ? "Connected" : "Not connected"}
            </Badge>
            {!capabilities.googleOauthAvailable && (
              <Badge tone="warning">Provider unavailable</Badge>
            )}
          </div>
          <p className="mt-2 text-sm leading-6 text-muted">
            {capabilities.googleOauthAvailable
              ? "Link Google after a recent sign-in. Disconnecting is allowed only when a password remains available."
              : "Google OAuth credentials are not configured in this environment."}
          </p>
        </div>
        {capabilities.googleConnected ? (
          <Button
            loading={busy}
            loadingLabel="Disconnecting…"
            onClick={() => void disconnect()}
            variant="secondary"
          >
            <Unlink aria-hidden="true" className="size-4" /> Disconnect
          </Button>
        ) : capabilities.googleOauthAvailable ? (
          <Link
            className={cn(buttonStyles.base, buttonStyles.primary)}
            href="/api/v1/auth/google/start?returnTo=%2Fsettings%2Fconnections&link=true"
          >
            Connect Google
          </Link>
        ) : null}
      </div>
    </Card>
  );
}
