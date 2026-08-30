"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";

import { Alert, Button, TextField } from "@rezumi/ui";

import {
  AuthRequestError,
  authErrorMessage,
  resendVerification,
  verifyEmail,
} from "../api/auth-api";
import { AuthPageShell } from "../components/auth-page-shell";
import { FormErrorSummary } from "../components/form-error-summary";
import { validateEmail } from "../validation/auth-validation";

type VerificationState = "checking" | "expired" | "missing" | "success";

function takeFragmentToken(): string | undefined {
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

export function VerifyEmailView() {
  const [state, setState] = useState<VerificationState>("checking");
  const [failure, setFailure] = useState<string>();
  const [emailError, setEmailError] = useState<string>();
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);

  useEffect(() => {
    queueMicrotask(() => {
      const token = takeFragmentToken();
      if (!token) {
        setState("missing");
        return;
      }
      void verifyEmail(token)
        .then(() => setState("success"))
        .catch((error: unknown) => {
          if (
            error instanceof AuthRequestError &&
            new Set([400, 404, 410]).has(error.failure.status)
          ) {
            setState("expired");
          } else {
            setFailure(
              authErrorMessage(
                error,
                "We couldn’t verify the email. Try again.",
              ),
            );
            setState("expired");
          }
        });
    });
  }, []);

  async function onResend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = String(new FormData(event.currentTarget).get("email") ?? "");
    const validationError = validateEmail(email);
    setEmailError(validationError);
    setFailure(undefined);
    if (validationError) return;

    setResending(true);
    try {
      await resendVerification(email.trim());
      setResent(true);
    } catch (error) {
      setFailure(
        authErrorMessage(error, "We couldn’t request a new verification link."),
      );
    } finally {
      setResending(false);
    }
  }

  return (
    <AuthPageShell
      description="Verification links are short-lived and single-use. Meridian does not expose whether another address has an account."
      eyebrow="Email verification"
      title={state === "success" ? "Email verified" : "Verify your email"}
    >
      <div className="min-h-80">
        {state === "checking" ? (
          <p aria-live="polite" className="text-sm text-muted" role="status">
            Verifying your email…
          </p>
        ) : state === "success" ? (
          <div className="space-y-5">
            <Alert title="Your email is verified" tone="success">
              You can now sign in and continue the protected onboarding flow.
            </Alert>
            <Link className="font-bold text-info-strong" href="/login">
              Continue to sign in
            </Link>
          </div>
        ) : resent ? (
          <div className="space-y-5">
            <Alert title="Verification email requested" tone="success">
              If the address is eligible, a new link will arrive. The same
              response is shown for every address.
            </Alert>
            <Link className="font-bold text-info-strong" href="/login">
              Return to sign in
            </Link>
          </div>
        ) : (
          <form className="space-y-5" noValidate onSubmit={onResend}>
            <Alert title="This verification link can’t be used" tone="warning">
              It may be expired, already used, or incomplete. Enter your email
              to request a new link.
            </Alert>
            <FormErrorSummary message={failure} />
            <TextField
              autoCapitalize="none"
              autoComplete="email"
              error={emailError}
              id="email"
              inputMode="email"
              label="Email address"
              maxLength={254}
              name="email"
              required
              spellCheck={false}
              type="email"
            />
            <Button
              className="w-full"
              loading={resending}
              loadingLabel="Requesting link…"
              type="submit"
            >
              Send a new verification link
            </Button>
          </form>
        )}
      </div>
    </AuthPageShell>
  );
}
