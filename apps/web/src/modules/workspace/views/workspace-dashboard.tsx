import {
  ArrowRight,
  BadgeCheck,
  FileHeart,
  ShieldCheck,
  UserRoundCheck,
} from "lucide-react";
import Link from "next/link";

import {
  Alert,
  Badge,
  buttonStyles,
  Card,
  CardHeader,
  cn,
  EmptyState,
  ScoreRing,
} from "@careeros/ui";

type DashboardResumeHealth =
  | { kind: "empty" }
  | { kind: "error" }
  | { filename: string; kind: "deleting" }
  | { filename: string; kind: "failed" | "processing" }
  | { documentId: string; filename: string; kind: "review" }
  | {
      analysisId: string;
      disclaimer: string;
      filename: string;
      kind: "report";
      score: number | null;
      scoreBand: "developing" | "needsAttention" | "strong" | null;
    };

export function WorkspaceDashboard({
  displayName,
  onboardingComplete,
  resumeHealth = { kind: "empty" },
}: {
  displayName: string;
  onboardingComplete: boolean;
  resumeHealth?: DashboardResumeHealth;
}) {
  return (
    <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
      <header className="mb-6">
        <Badge tone="success">
          <ShieldCheck aria-hidden="true" className="size-3.5" /> Verified
          account
        </Badge>
        <h1 className="mt-3 text-2xl font-black tracking-[-0.035em] text-foreground sm:text-3xl">
          Welcome to your CareerOS workspace, {displayName}.
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          This protected workspace shows only your persisted account and resume
          state. No fictional metrics appear in authenticated views.
        </p>
      </header>

      <div className="grid gap-5 lg:grid-cols-[0.85fr_1.15fr]">
        <Card>
          <CardHeader
            action={
              <Badge tone={onboardingComplete ? "success" : "warning"}>
                {onboardingComplete ? "Complete" : "In progress"}
              </Badge>
            }
            description="Your saved account setup"
            title="Onboarding"
          />
          <div className="p-5 sm:p-6">
            <span className="grid size-11 place-items-center rounded-xl bg-primary-soft text-primary">
              <UserRoundCheck aria-hidden="true" className="size-5" />
            </span>
            <h2 className="mt-4 text-base font-extrabold text-foreground">
              {onboardingComplete
                ? "Your preferences are saved"
                : "Finish setting up your account"}
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted">
              You can revisit your target role and working preferences at any
              time. Resume upload and parsed-field review are now available from
              Resume Health.
            </p>
            <Link
              className={cn(buttonStyles.base, buttonStyles.secondary, "mt-5")}
              href="/onboarding"
            >
              {onboardingComplete ? "Review onboarding" : "Continue onboarding"}
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
          </div>
        </Card>

        <Card>
          <CardHeader
            action={
              <FileHeart aria-hidden="true" className="size-5 text-primary" />
            }
            description="Real state from your latest private document"
            title="Resume Health"
          />
          <div className="p-5 sm:p-6">
            {resumeHealth.kind === "empty" && (
              <EmptyState
                action={
                  <Link
                    className={cn(buttonStyles.base, buttonStyles.primary)}
                    href="/resume-health/account"
                  >
                    Upload a resume{" "}
                    <ArrowRight aria-hidden="true" className="size-4" />
                  </Link>
                }
                className="min-h-72 border-dashed shadow-none"
                description="Upload a real PDF or DOCX, review uncertain parsing, and calculate an explainable internal measurement."
                title="No resume data yet"
              />
            )}
            {resumeHealth.kind === "processing" && (
              <div className="min-h-72 rounded-2xl bg-slate-50 p-5">
                <Badge tone="warning">Processing</Badge>
                <h2 className="mt-4 font-extrabold">
                  Preparing {resumeHealth.filename}
                </h2>
                <p className="mt-2 text-sm leading-6 text-muted">
                  The file remains quarantined while the protected worker scans
                  and parses it.
                </p>
                <Link
                  className={cn(
                    buttonStyles.base,
                    buttonStyles.secondary,
                    "mt-5",
                  )}
                  href="/resume-health/account"
                >
                  View document status
                </Link>
              </div>
            )}
            {resumeHealth.kind === "deleting" && (
              <Alert title="Deletion in progress" tone="info">
                {resumeHealth.filename} is completing durable source and
                derivative cleanup. Refresh this page after the job finishes.
                <Link
                  className="mt-3 block font-bold underline"
                  href="/resume-health/account"
                >
                  Open Resume Health
                </Link>
              </Alert>
            )}
            {resumeHealth.kind === "review" && (
              <div className="min-h-72 rounded-2xl bg-primary-soft/25 p-5">
                <Badge tone="warning">Review required</Badge>
                <h2 className="mt-4 font-extrabold">Check the parsed fields</h2>
                <p className="mt-2 text-sm leading-6 text-muted">
                  CareerOS extracted structured information from{" "}
                  {resumeHealth.filename}. Confirm or correct it before
                  analysis.
                </p>
                <Link
                  className={cn(
                    buttonStyles.base,
                    buttonStyles.primary,
                    "mt-5",
                  )}
                  href={`/resume-health/account/review/${encodeURIComponent(resumeHealth.documentId)}`}
                >
                  Review parsed resume
                </Link>
              </div>
            )}
            {resumeHealth.kind === "failed" && (
              <Alert title="Document needs attention" tone="danger">
                {resumeHealth.filename} could not be safely processed. Open
                Resume Health to delete it or try a clean supported file.
                <Link
                  className="mt-3 block font-bold underline"
                  href="/resume-health/account"
                >
                  Open Resume Health
                </Link>
              </Alert>
            )}
            {resumeHealth.kind === "error" && (
              <Alert title="Resume Health unavailable" tone="danger">
                Your private resume state could not be loaded. No document was
                changed. Refresh the page or open Resume Health to try again.
                <Link
                  className="mt-3 block font-bold underline"
                  href="/resume-health/account"
                >
                  Open Resume Health
                </Link>
              </Alert>
            )}
            {resumeHealth.kind === "report" && (
              <div className="grid min-h-72 gap-5 md:grid-cols-[10rem_1fr] md:items-center">
                <div className="flex justify-center">
                  {resumeHealth.score === null ? (
                    <span className="grid size-32 place-items-center rounded-full border-8 border-slate-200 text-center text-xs font-black text-muted">
                      Score unavailable
                    </span>
                  ) : (
                    <ScoreRing
                      label="Resume Health Score"
                      score={resumeHealth.score}
                      tone={
                        resumeHealth.scoreBand === "strong"
                          ? "success"
                          : "warning"
                      }
                    />
                  )}
                </div>
                <div>
                  <Badge
                    tone={
                      resumeHealth.scoreBand === "strong"
                        ? "success"
                        : "warning"
                    }
                  >
                    Internal CareerOS measure
                  </Badge>
                  <h2 className="mt-3 font-extrabold">
                    Latest report for {resumeHealth.filename}
                  </h2>
                  <p className="mt-2 text-xs leading-5 text-muted">
                    {resumeHealth.disclaimer}
                  </p>
                  <Link
                    className={cn(
                      buttonStyles.base,
                      buttonStyles.primary,
                      "mt-5",
                    )}
                    href={`/resume-health/account/report/${encodeURIComponent(resumeHealth.analysisId)}`}
                  >
                    Open full report{" "}
                    <ArrowRight aria-hidden="true" className="size-4" />
                  </Link>
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>

      <section aria-labelledby="account-ready-heading" className="mt-5">
        <Card className="p-5 sm:p-6">
          <div className="flex items-start gap-3">
            <BadgeCheck
              aria-hidden="true"
              className="mt-0.5 size-5 shrink-0 text-success"
            />
            <div>
              <h2
                className="font-extrabold text-foreground"
                id="account-ready-heading"
              >
                Your account foundation is ready
              </h2>
              <p className="mt-1 text-sm leading-6 text-muted">
                Maintain a structured career record, connect provenance-rich
                evidence, and capture achievements without requiring a resume.
              </p>
              <div className="mt-3 flex flex-wrap gap-4">
                <Link
                  className="inline-flex text-sm font-bold text-primary"
                  href="/career-profile"
                >
                  Open Career Profile{" "}
                  <ArrowRight aria-hidden="true" className="ml-1 size-4" />
                </Link>
                <Link
                  className="inline-flex text-sm font-bold text-primary"
                  href="/evidence"
                >
                  Open Evidence Vault{" "}
                  <ArrowRight aria-hidden="true" className="ml-1 size-4" />
                </Link>
              </div>
            </div>
          </div>
        </Card>
      </section>
    </main>
  );
}
