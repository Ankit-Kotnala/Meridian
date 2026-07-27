import { ArrowRight, FileSearch, UserRoundPlus } from "lucide-react";
import Link from "next/link";

import { Alert, buttonStyles, cn } from "@careeros/ui";

import { AuthPageShell } from "../components/auth-page-shell";

export function GetStartedView() {
  return (
    <AuthPageShell
      description="Create a protected account or run one short-lived guest Resume Health check through the same secure document pipeline."
      eyebrow="Get started"
      title="Choose how to begin"
    >
      <div className="space-y-5">
        <div className="border-b border-line pb-5">
          <span className="grid size-10 place-items-center rounded-[var(--radius-control)] bg-primary-soft text-primary">
            <UserRoundPlus aria-hidden="true" className="size-5" />
          </span>
          <h2 className="mt-4 font-semibold text-foreground">
            Create a private account
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            Verify your email, save onboarding preferences, and manage protected
            sessions.
          </p>
          <Link
            className={cn(
              buttonStyles.base,
              buttonStyles.primary,
              "mt-4 w-full",
            )}
            href="/register"
          >
            Create account <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        </div>

        <div className="border-b border-line pb-5">
          <span className="grid size-10 place-items-center rounded-[var(--radius-control)] bg-surface-subtle text-muted">
            <FileSearch aria-hidden="true" className="size-5" />
          </span>
          <h2 className="mt-4 font-semibold text-foreground">
            Guest resume health
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            Upload one PDF or DOCX, review uncertain parsing, and receive a
            limited report that expires unless you explicitly save it.
          </p>
          <Link
            className={cn(
              buttonStyles.base,
              buttonStyles.secondary,
              "mt-4 w-full",
            )}
            href="/resume-health/guest"
          >
            Check a resume as a guest
          </Link>
        </div>

        <Alert title="Real document state only" tone="info">
          CareerOS displays a report only after a real document passes
          admission, parsing, explicit review, and deterministic analysis.
        </Alert>
      </div>
    </AuthPageShell>
  );
}
