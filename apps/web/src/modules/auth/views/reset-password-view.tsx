"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";

import { Alert, Button } from "@careeros/ui";

import {
  AuthRequestError,
  authErrorMessage,
  resetPassword,
} from "../api/auth-api";
import { AuthPageShell } from "../components/auth-page-shell";
import { FormErrorSummary } from "../components/form-error-summary";
import { PasswordField } from "../components/password-field";
import { validatePassword } from "../validation/auth-validation";

function fragmentToken(): string | undefined {
  const value = new URLSearchParams(window.location.hash.slice(1))
    .get("token")
    ?.trim();
  window.history.replaceState(
    null,
    "",
    `${window.location.pathname}${window.location.search}`,
  );
  return value || undefined;
}

export function ResetPasswordView() {
  const [token, setToken] = useState<string>();
  const [ready, setReady] = useState(false);
  const [passwordError, setPasswordError] = useState<string>();
  const [failure, setFailure] = useState<string>();
  const [expired, setExpired] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [complete, setComplete] = useState(false);

  useEffect(() => {
    queueMicrotask(() => {
      setToken(fragmentToken());
      setReady(true);
    });
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password") ?? "");
    const confirmation = String(form.get("confirmation") ?? "");
    const validationError = validatePassword(password);
    const nextError =
      validationError ??
      (password !== confirmation ? "The passwords do not match." : undefined);
    setPasswordError(nextError);
    setFailure(undefined);
    if (nextError) return;

    setSubmitting(true);
    try {
      await resetPassword(token, password);
      setToken(undefined);
      setComplete(true);
    } catch (error) {
      if (
        error instanceof AuthRequestError &&
        new Set([400, 404, 410]).has(error.failure.status)
      ) {
        setExpired(true);
      } else {
        setFailure(
          authErrorMessage(error, "We couldn’t reset the password. Try again."),
        );
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthPageShell
      description="Choose a new password. A successful reset revokes active sessions so stolen credentials cannot remain signed in."
      eyebrow="Account recovery"
      title="Choose a new password"
    >
      {!ready ? (
        <p aria-live="polite" className="text-sm text-muted" role="status">
          Preparing the secure reset form…
        </p>
      ) : complete ? (
        <div className="space-y-5">
          <Alert title="Password updated" tone="success">
            Your previous sessions have been invalidated. Sign in again with the
            new password.
          </Alert>
          <Link className="font-bold text-primary" href="/login">
            Continue to sign in
          </Link>
        </div>
      ) : expired || !token ? (
        <div className="space-y-5">
          <Alert title="This reset link can’t be used" tone="warning">
            It may be expired, already used, or incomplete. Request a new link
            without sharing the old one.
          </Alert>
          <Link className="font-bold text-primary" href="/forgot-password">
            Request a new reset link
          </Link>
        </div>
      ) : (
        <form className="space-y-5" noValidate onSubmit={onSubmit}>
          <FormErrorSummary message={failure} />
          <PasswordField
            autoComplete="new-password"
            error={passwordError}
            hint="Use 12–128 characters. A password manager is recommended."
            id="password"
            label="New password"
            maxLength={128}
            minLength={12}
            name="password"
            required
          />
          <PasswordField
            autoComplete="new-password"
            id="confirmation"
            label="Confirm new password"
            maxLength={128}
            minLength={12}
            name="confirmation"
            required
          />
          <Button
            className="w-full"
            loading={submitting}
            loadingLabel="Updating password…"
            type="submit"
          >
            Update password
          </Button>
        </form>
      )}
    </AuthPageShell>
  );
}
