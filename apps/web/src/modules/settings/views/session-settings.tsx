"use client";

import { Clock3, Laptop, LogOut, RefreshCcw, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
} from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  getSessions,
  revokeAllSessions,
  revokeSession,
  type SessionState,
} from "../api/settings-api";

function dateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? "Unknown"
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

export function SessionSettings() {
  const router = useRouter();
  const [sessions, setSessions] = useState<SessionState[]>();
  const [failure, setFailure] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [busySession, setBusySession] = useState<string>();
  const [allBusy, setAllBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const saved = await getSessions();
      setFailure(undefined);
      setSessions(saved);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t load your active sessions."),
      );
    }
  }, []);
  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  async function onRevoke(session: SessionState) {
    setBusySession(session.id);
    setFailure(undefined);
    setNotice(undefined);
    try {
      await revokeSession(session.id);
      if (session.current) {
        router.replace("/login");
        router.refresh();
        return;
      }
      setSessions((current) =>
        current?.filter((item) => item.id !== session.id),
      );
      setNotice(`${session.deviceLabel} was signed out.`);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t revoke that session."),
      );
    } finally {
      setBusySession(undefined);
    }
  }

  async function onRevokeAll() {
    setAllBusy(true);
    setFailure(undefined);
    try {
      await revokeAllSessions();
      router.replace("/login");
      router.refresh();
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t sign out all sessions."),
      );
    } finally {
      setAllBusy(false);
    }
  }

  if (!sessions && !failure) return <LoadingSkeleton variant="list" />;
  if (!sessions)
    return (
      <ErrorState
        description={failure ?? "We couldn’t load your active sessions."}
        onRetry={load}
        title="Sessions unavailable"
      />
    );

  return (
    <Card className="p-5 sm:p-7">
      <div className="flex flex-col gap-4 border-b border-line pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-extrabold text-foreground">
            Active sessions
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
            Review devices that can access this account. Revoking a session
            invalidates its stored session and refresh material on the server.
          </p>
        </div>
        <Button
          loading={allBusy}
          loadingLabel="Signing out sessions…"
          onClick={() => void onRevokeAll()}
          variant="secondary"
        >
          <LogOut aria-hidden="true" className="size-4" /> Sign out all sessions
        </Button>
      </div>

      {failure && (
        <Alert className="mt-5" title="Session action failed" tone="danger">
          {failure}
          <Button className="mt-3" onClick={load} variant="secondary">
            <RefreshCcw aria-hidden="true" className="size-4" /> Reload sessions
          </Button>
        </Alert>
      )}
      {notice && <Alert className="mt-5" title={notice} tone="success" />}

      {sessions.length === 0 ? (
        <EmptyState
          className="mt-5"
          description="No active session records were returned. Sign in again before managing sessions."
          title="No active sessions"
        />
      ) : (
        <ul className="mt-5 divide-y divide-line">
          {sessions.map((session) => (
            <li
              className="flex flex-col gap-4 py-5 first:pt-0 sm:flex-row sm:items-center"
              key={session.id}
            >
              <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
                <Laptop aria-hidden="true" className="size-5" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-extrabold text-foreground">
                    {session.deviceLabel}
                  </p>
                  {session.current && (
                    <Badge tone="success">Current session</Badge>
                  )}
                  <Badge tone="neutral">
                    {session.authMethod === "google" ? "Google" : "Password"}
                  </Badge>
                </div>
                <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
                  <span className="inline-flex items-center gap-1.5">
                    <Clock3 aria-hidden="true" className="size-3.5" /> Last
                    active {dateTime(session.lastSeenAt)}
                  </span>
                  <span>Expires {dateTime(session.expiresAt)}</span>
                </div>
              </div>
              <Button
                aria-label={`Revoke ${session.deviceLabel}`}
                loading={busySession === session.id}
                loadingLabel="Revoking…"
                onClick={() => void onRevoke(session)}
                variant={session.current ? "ghost" : "secondary"}
              >
                <ShieldCheck aria-hidden="true" className="size-4" />
                {session.current ? "Sign out this session" : "Revoke"}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
