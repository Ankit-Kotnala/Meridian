"use client";

import { MailCheck } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Alert, Button, TextField } from "@careeros/ui";

import { authErrorMessage, forgotPassword } from "../api/auth-api";
import { AuthPageShell } from "../components/auth-page-shell";
import { FormErrorSummary } from "../components/form-error-summary";
import { validateEmail } from "../validation/auth-validation";

export function ForgotPasswordView() {
  const [emailError, setEmailError] = useState<string>();
  const [failure, setFailure] = useState<string>();
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = String(new FormData(event.currentTarget).get("email") ?? "");
    const error = validateEmail(email);
    setEmailError(error);
    setFailure(undefined);
    if (error) return;

    setSubmitting(true);
    try {
      await forgotPassword(email.trim());
      setSubmitted(true);
    } catch (requestError) {
      setFailure(
        authErrorMessage(
          requestError,
          "We couldn’t request a reset link. Try again.",
        ),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthPageShell
      description="Request a short-lived, single-use password reset link. The response never reveals whether an account exists."
      eyebrow="Account recovery"
      title={submitted ? "Check your email" : "Reset your password"}
    >
      {submitted ? (
        <div className="space-y-5">
          <Alert title="Reset email requested" tone="success">
            If the address belongs to an eligible account, a password reset link
            will arrive. The same response is shown for every address.
          </Alert>
          <div className="rounded-xl bg-slate-50 p-4 text-sm leading-6 text-muted">
            <MailCheck
              aria-hidden="true"
              className="mb-2 size-5 text-primary"
            />
            Use only the newest reset email. A successful reset invalidates
            existing sessions.
          </div>
          <Link className="text-sm font-bold text-primary" href="/login">
            Return to sign in
          </Link>
        </div>
      ) : (
        <form className="space-y-5" noValidate onSubmit={onSubmit}>
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
            loading={submitting}
            loadingLabel="Requesting link…"
            type="submit"
          >
            Send reset link
          </Button>
          <p className="text-center text-sm">
            <Link className="font-bold text-primary" href="/login">
              Return to sign in
            </Link>
          </p>
        </form>
      )}
    </AuthPageShell>
  );
}
