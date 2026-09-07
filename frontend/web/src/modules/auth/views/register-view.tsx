"use client";

import { ArrowRight, MailCheck } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Alert, Button, TextField } from "@rezumi/ui";

import {
  authErrorMessage,
  googleAuthorizationUrl,
  registerAccount,
} from "../api/auth-api";
import { AuthPageShell } from "../components/auth-page-shell";
import { FormErrorSummary } from "../components/form-error-summary";
import { GoogleMark } from "../components/google-mark";
import { PasswordField } from "../components/password-field";
import {
  validateDisplayName,
  validateEmail,
  validatePassword,
  type FieldErrors,
} from "../validation/auth-validation";

export function RegisterView() {
  const [errors, setErrors] = useState<FieldErrors>({});
  const [failure, setFailure] = useState<string>();
  const [submitting, setSubmitting] = useState(false);
  const [googleSubmitting, setGoogleSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const displayName = String(form.get("displayName") ?? "");
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");
    const nextErrors = {
      ...(validateDisplayName(displayName)
        ? { displayName: validateDisplayName(displayName)! }
        : {}),
      ...(validateEmail(email) ? { email: validateEmail(email)! } : {}),
      ...(validatePassword(password)
        ? { password: validatePassword(password)! }
        : {}),
    };
    setErrors(nextErrors);
    setFailure(undefined);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    try {
      await registerAccount({
        displayName: displayName.trim(),
        email: email.trim(),
        password,
      });
      setSubmitted(true);
    } catch (error) {
      setFailure(
        authErrorMessage(
          error,
          "We couldn’t create the account. Check your connection and try again.",
        ),
      );
    } finally {
      setSubmitting(false);
    }
  }

  function onGoogle() {
    setGoogleSubmitting(true);
    setFailure(undefined);
    window.location.assign(googleAuthorizationUrl("/dashboard"));
  }

  return (
    <AuthPageShell
      description="Create a private account. We’ll send a verification link before you can enter the protected workspace."
      eyebrow="Create account"
      title={submitted ? "Check your email" : "Start your Meridian account"}
    >
      {submitted ? (
        <div className="space-y-5">
          <Alert title="Verification email requested" tone="success">
            If the address can receive Meridian mail, a short-lived verification
            link will arrive. This message is the same for existing and new
            accounts.
          </Alert>
          <div className="rounded-xl bg-surface-subtle p-4 text-sm leading-6 text-muted">
            <MailCheck
              aria-hidden="true"
              className="mb-2 size-5 text-primary"
            />
            Open the link in that email, then return to sign in. Links expire
            and can be used only once.
          </div>
          <Link
            className="inline-flex items-center gap-2 text-sm font-bold text-info-strong"
            href="/login"
          >
            Continue to sign in{" "}
            <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        </div>
      ) : (
        <form className="space-y-4" noValidate onSubmit={onSubmit}>
          <FormErrorSummary message={failure} />
          <TextField
            autoComplete="name"
            error={errors.displayName}
            className="min-h-11"
            id="displayName"
            label="Name"
            maxLength={100}
            name="displayName"
            placeholder="The name you want Meridian to use"
            required
          />
          <TextField
            autoCapitalize="none"
            autoComplete="email"
            error={errors.email}
            className="min-h-11"
            id="email"
            inputMode="email"
            label="Email address"
            maxLength={254}
            name="email"
            required
            spellCheck={false}
            type="email"
          />
          <PasswordField
            autoComplete="new-password"
            error={errors.password}
            className="min-h-11"
            hint="Use 12–128 characters. A password manager is recommended."
            id="password"
            label="Password"
            maxLength={128}
            minLength={12}
            name="password"
            required
          />
          <p className="text-xs leading-5 text-muted">
            By creating an account, you acknowledge the current privacy and
            account-processing notices. Optional data-use choices remain off
            until you grant them in Settings.
          </p>
          <Button
            className="w-full min-h-11 rounded-lg text-[0.9375rem]"
            loading={submitting}
            loadingLabel="Creating account…"
            type="submit"
          >
            Create account
          </Button>
          <div className="flex items-center gap-3" aria-hidden="true">
            <span className="h-px flex-1 bg-line" />
            <span className="text-[0.6875rem] font-bold uppercase tracking-[0.2em] text-muted">
              or
            </span>
            <span className="h-px flex-1 bg-line" />
          </div>
          <Button
            className="w-full min-h-11 rounded-lg text-[0.9375rem]"
            loading={googleSubmitting}
            loadingLabel="Opening Google..."
            onClick={onGoogle}
            type="button"
            variant="secondary"
          >
            <GoogleMark /> Continue with Google
          </Button>
          <p className="pt-1 text-center text-sm text-muted">
            Already have an account?{" "}
            <Link className="font-bold text-info-strong" href="/login">
              Sign in
            </Link>
          </p>
        </form>
      )}
    </AuthPageShell>
  );
}
