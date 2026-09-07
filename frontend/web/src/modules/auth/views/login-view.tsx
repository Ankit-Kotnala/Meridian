"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button, TextField } from "@rezumi/ui";

import {
  authErrorMessage,
  googleAuthorizationUrl,
  login,
} from "../api/auth-api";
import { AuthPageShell } from "../components/auth-page-shell";
import { FormErrorSummary } from "../components/form-error-summary";
import { GoogleMark } from "../components/google-mark";
import { PasswordField } from "../components/password-field";
import { validateEmail, type FieldErrors } from "../validation/auth-validation";

function safeReturnTo(value: string | null): string {
  if (
    !value ||
    value.length > 200 ||
    value.includes("\\") ||
    /[\u0000-\u001f]/.test(value)
  )
    return "/dashboard";
  const allowedRoots = [
    "/dashboard",
    "/onboarding",
    "/settings",
    "/resume-health/account",
    "/resume-health/guest/report",
  ];
  return allowedRoots.some(
    (root) =>
      value === root ||
      value.startsWith(`${root}/`) ||
      value.startsWith(`${root}?`),
  )
    ? value
    : "/dashboard";
}

export function LoginView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnTo = safeReturnTo(searchParams.get("returnTo"));
  const [errors, setErrors] = useState<FieldErrors>({});
  const [failure, setFailure] = useState<string>();
  const [submitting, setSubmitting] = useState(false);
  const [googleSubmitting, setGoogleSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");
    const nextErrors = {
      ...(validateEmail(email) ? { email: validateEmail(email)! } : {}),
      ...(!password ? { password: "Enter your password." } : {}),
    };
    setErrors(nextErrors);
    setFailure(undefined);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    try {
      await login({ email: email.trim(), password });
      router.replace(returnTo);
      router.refresh();
    } catch (error) {
      const message =
        error instanceof Error &&
        "failure" in error &&
        (error as { failure?: { status?: number } }).failure?.status === 401
          ? "The email or password is incorrect, or the account is not ready to sign in."
          : authErrorMessage(error, "We couldn't sign you in. Try again.");
      setFailure(message);
    } finally {
      setSubmitting(false);
    }
  }

  function onGoogle() {
    setGoogleSubmitting(true);
    setFailure(undefined);
    window.location.assign(googleAuthorizationUrl(returnTo));
  }

  return (
    <AuthPageShell
      description="Use your verified account to open the protected workspace and manage active sessions."
      eyebrow="Welcome back"
      title="Sign in to Meridian"
    >
      <form className="space-y-4" noValidate onSubmit={onSubmit}>
        <FormErrorSummary message={failure} />
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
          autoComplete="current-password"
          error={errors.password}
          className="min-h-11"
          id="password"
          label="Password"
          maxLength={128}
          name="password"
          required
        />
        <div className="flex justify-end">
          <Link
            className="text-sm font-semibold text-info-strong hover:text-info"
            href="/forgot-password"
          >
            Forgot password?
          </Link>
        </div>
        <Button
          className="w-full min-h-11 rounded-lg text-[0.9375rem]"
          loading={submitting}
          loadingLabel="Signing in..."
          type="submit"
        >
          Sign in
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
          New to Meridian?{" "}
          <Link className="font-bold text-info-strong" href="/register">
            Create an account
          </Link>
        </p>
      </form>
    </AuthPageShell>
  );
}
