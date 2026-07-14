import { ArrowRight, FileSearch, UserRoundPlus } from "lucide-react";
import Link from "next/link";

import { Alert, buttonStyles, Card, cn } from "@careeros/ui";

import { AuthPageShell } from "../components/auth-page-shell";

export function GetStartedView() {
  return (
    <AuthPageShell
      description="Choose an account path now. The limited guest resume-health handoff remains unavailable until secure document processing ships in Phase 2."
      eyebrow="Get started"
      title="Choose how to begin"
    >
      <div className="space-y-4">
        <Card className="p-5">
          <span className="grid size-10 place-items-center rounded-xl bg-primary-soft text-primary">
            <UserRoundPlus aria-hidden="true" className="size-5" />
          </span>
          <h2 className="mt-4 font-extrabold text-foreground">
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
        </Card>

        <Card className="p-5">
          <span className="grid size-10 place-items-center rounded-xl bg-slate-100 text-muted">
            <FileSearch aria-hidden="true" className="size-5" />
          </span>
          <h2 className="mt-4 font-extrabold text-foreground">
            Guest resume health
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            Guest document upload is a Phase 2 feature. CareerOS does not
            collect a resume before its secure upload and deletion controls are
            implemented.
          </p>
          <Link
            className={cn(
              buttonStyles.base,
              buttonStyles.secondary,
              "mt-4 w-full",
            )}
            href="/resume-health"
          >
            Read how resume health will work
          </Link>
        </Card>

        <Alert title="No upload is simulated" tone="info">
          Skipping this handoff does not create a document, analysis, or score.
        </Alert>
      </div>
    </AuthPageShell>
  );
}
