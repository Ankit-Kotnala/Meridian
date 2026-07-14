import {
  ArrowRight,
  BadgeCheck,
  FileHeart,
  ShieldCheck,
  UserRoundCheck,
} from "lucide-react";
import Link from "next/link";

import {
  Badge,
  buttonStyles,
  Card,
  CardHeader,
  cn,
  EmptyState,
} from "@careeros/ui";

export function WorkspaceDashboard({
  displayName,
  onboardingComplete,
}: {
  displayName: string;
  onboardingComplete: boolean;
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
          This protected workspace contains only your account state. Career data
          and scores appear only after you add real information in later phases.
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
              time. Resume upload is an explicit Phase 2 handoff.
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
            description="No fictional metrics are shown in a protected account"
            title="Resume workspace"
          />
          <div className="p-5 sm:p-6">
            <EmptyState
              className="min-h-72 border-dashed shadow-none"
              description="Resume upload and health analysis begin in Phase 2. Until you provide a real document, CareerOS will not display sample scores or invented activity."
              title="No resume data yet"
            />
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
                Manage profile details, consent choices, and active sessions in
                Settings. Future product modules remain unavailable until their
                verified implementation phases.
              </p>
              <Link
                className="mt-3 inline-flex text-sm font-bold text-primary"
                href="/settings"
              >
                Open settings{" "}
                <ArrowRight aria-hidden="true" className="ml-1 size-4" />
              </Link>
            </div>
          </div>
        </Card>
      </section>
    </main>
  );
}
