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

function GoogleMark() {
  return (
    <svg aria-hidden="true" className="size-5 shrink-0" viewBox="0 0 24 24">
      <path
        d="M21.35 10.91H12v2.94h5.35C16.42 16.68 14.47 18 12 18a6 6 0 1 1 0-12c1.63 0 3.1.58 4.25 1.55l2.12-2.12A9.01 9.01 0 0 0 12 3a9 9 0 1 0 9 9c0-.39-.03-.7-.07-1.09Z"
        fill="#4285F4"
      />
      <path
        d="m6.53 14.29-2.14 1.64A8.97 8.97 0 0 0 12 21a8.77 8.77 0 0 0 6.02-2.3l-2.55-2.03A5.95 5.95 0 0 1 12 18a6 6 0 0 1-5.47-3.71Z"
        fill="#34A853"
      />
      <path
        d="M4.38 9.39a9.1 9.1 0 0 0-.48 2.86c0 .8.11 1.58.31 2.29l2.32-1.8a5.9 5.9 0 0 1-.14-1.34c0-.45.05-.9.15-1.31L4.38 9.39Z"
        fill="#FBBC05"
      />
      <path
        d="M12 6.02c1.79 0 3.4.63 4.68 1.86l2.14-2.14A8.99 8.99 0 0 0 12 3c-2.92 0-5.48 1.4-7.15 3.56L7.43 8.6A5.97 5.97 0 0 1 12 6.02Z"
        fill="#EA4335"
      />
    </svg>
  );
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
      <form className="space-y-5" noValidate onSubmit={onSubmit}>
        <FormErrorSummary message={failure} />
        <TextField
          autoCapitalize="none"
          autoComplete="email"
          error={errors.email}
          className="min-h-12 bg-white/95 shadow-[0_1px_0_rgba(255,255,255,0.85)_inset]"
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
          className="min-h-12 bg-white/95 shadow-[0_1px_0_rgba(255,255,255,0.85)_inset]"
          id="password"
          label="Password"
          maxLength={128}
          name="password"
          required
        />
        <div className="flex justify-end pt-1">
          <Link
            className="text-sm font-semibold text-info-strong hover:text-info"
            href="/forgot-password"
          >
            Forgot password?
          </Link>
        </div>
        <Button
          className="w-full min-h-12 rounded-[1rem] border-0 bg-[linear-gradient(135deg,#0f6d62_0%,#0c4f49_100%)] text-base shadow-[0_18px_40px_-22px_rgba(9,79,72,0.82)] hover:border-0 hover:bg-[linear-gradient(135deg,#10786c_0%,#0b5c55_100%)]"
          loading={submitting}
          loadingLabel="Signing in..."
          type="submit"
        >
          Sign in
        </Button>
        <div className="flex items-center gap-3 px-1 pt-1" aria-hidden="true">
          <span className="h-px flex-1 bg-line" />
          <span className="text-xs font-bold uppercase tracking-[0.22em] text-muted">
            or
          </span>
          <span className="h-px flex-1 bg-line" />
        </div>
        <Button
          className="w-full min-h-12 rounded-[1rem] border-line-strong bg-white text-base shadow-none hover:border-foreground/30 hover:bg-surface-subtle/70"
          loading={googleSubmitting}
          loadingLabel="Opening Google..."
          onClick={onGoogle}
          type="button"
          variant="secondary"
        >
          <GoogleMark /> Continue with Google
        </Button>
        <p className="text-center text-sm text-muted">
          New to Meridian?{" "}
          <Link className="font-bold text-info-strong" href="/register">
            Create an account
          </Link>
        </p>
      </form>
    </AuthPageShell>
  );
}
