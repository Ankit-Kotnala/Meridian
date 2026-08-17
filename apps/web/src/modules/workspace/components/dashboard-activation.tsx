import {
  ArrowRight,
  BadgeCheck,
  Check,
  CircleDashed,
  FileSearch,
  HelpCircle,
  Loader,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  UserRoundCheck,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import { Badge, buttonStyles, cn } from "@rezumi/ui";

import type { DashboardResumeHealth } from "./dashboard-resume-state";
import type {
  DashboardCount,
  DashboardSummary,
} from "../server/dashboard-summary";

type StepState = "current" | "done" | "pending" | "unknown";

export type ActivationStep = {
  action?: { href: string; label: string };
  description: string;
  id: string;
  label: string;
  state: StepState;
};

function isPositive(count: DashboardCount): boolean | undefined {
  if (count.kind === "unavailable") return undefined;
  return count.value > 0;
}

/**
 * Project cross-module state into the chain a resume travels through. This is a
 * read-only projection: no step ever advances itself, and a step whose owning
 * endpoint failed reports `unknown` rather than claiming incomplete.
 */
export function activationChain(
  resumeHealth: DashboardResumeHealth,
  summary: DashboardSummary,
): readonly ActivationStep[] {
  const hasRecord = isPositive(summary.record.experiences);
  const hasImports = isPositive(summary.activation.pendingImports);
  const hasJobs = isPositive(summary.activation.jobs);
  const settled = resumeHealth.kind === "report";
  const stalled =
    resumeHealth.kind === "failed" ||
    resumeHealth.kind === "error" ||
    resumeHealth.kind === "deleting";

  const raw: readonly (Omit<ActivationStep, "state"> & {
    done: boolean | undefined;
  })[] = [
    {
      description:
        "Your file is scanned for malware in a quarantined worker before anything reads it.",
      done: resumeHealth.kind !== "empty",
      id: "resume",
      label: "Resume added and scanned",
      ...(resumeHealth.kind === "empty"
        ? { action: { href: "/resume-health/account", label: "Upload" } }
        : {}),
    },
    {
      description:
        "You confirm or correct the extracted fields. Uncertain parsing never becomes career data on its own.",
      done: settled,
      id: "review",
      label: "Parsed fields reviewed",
      ...(resumeHealth.kind === "review"
        ? {
            action: {
              href: `/resume-health/account/review/${encodeURIComponent(resumeHealth.documentId)}`,
              label: "Review fields",
            },
          }
        : stalled
          ? { action: { href: "/resume-health/account", label: "Resolve" } }
          : {}),
    },
    {
      description:
        "An explainable internal measurement of how well the document reads to machines and recruiters.",
      done: settled,
      id: "report",
      label: "Resume health report ready",
      ...(settled
        ? {
            action: {
              href: `/resume-health/account/report/${encodeURIComponent(resumeHealth.analysisId)}`,
              label: "Open report",
            },
          }
        : {}),
    },
    {
      description:
        "Approved facts become experiences, skills, and evidence that later documents are allowed to cite.",
      done: hasRecord,
      id: "record",
      label: "Career record populated",
      ...(hasImports === true
        ? {
            action: {
              href: "/career-profile/imports",
              label: "Accept facts",
            },
          }
        : hasRecord === false
          ? { action: { href: "/career-profile", label: "Add a role" } }
          : {}),
    },
    {
      description:
        "Compare a real posting against your record to see matched requirements and honest gaps.",
      done: hasJobs,
      id: "opportunity",
      label: "First opportunity compared",
      ...(hasJobs === false
        ? { action: { href: "/job-match", label: "Add a role posting" } }
        : {}),
    },
  ];

  let currentAssigned = false;
  return raw.map(({ done, ...step }) => {
    if (done === undefined) return { ...step, state: "unknown" as const };
    if (done) return { ...step, state: "done" as const };
    if (!currentAssigned) {
      currentAssigned = true;
      return { ...step, state: "current" as const };
    }
    return { ...step, state: "pending" as const };
  });
}

const stateVisual: Record<
  StepState,
  { className: string; icon: LucideIcon; label: string }
> = {
  current: {
    className: "border-primary bg-primary text-white",
    icon: Loader,
    label: "In progress",
  },
  done: {
    className: "border-success bg-success-soft text-success-strong",
    icon: Check,
    label: "Complete",
  },
  pending: {
    className: "border-line-strong bg-surface text-muted",
    icon: CircleDashed,
    label: "Not started",
  },
  unknown: {
    className: "border-line-strong bg-surface-subtle text-muted",
    icon: HelpCircle,
    label: "Status unavailable",
  },
};

export function ActivationChain({
  steps,
}: {
  steps: readonly ActivationStep[];
}) {
  const complete = steps.filter(({ state }) => state === "done").length;
  const unknown = steps.some(({ state }) => state === "unknown");

  const percent = Math.round((complete / steps.length) * 100);

  return (
    <section
      aria-labelledby="activation-heading"
      className="data-region p-5 sm:p-7"
    >
      <div className="grid gap-7 lg:grid-cols-[minmax(0,0.78fr)_minmax(0,1.22fr)]">
        <header>
          <p className="eyebrow flex items-center gap-1.5 !text-primary-strong">
            <Sparkles aria-hidden="true" className="size-3.5" />
            Getting your workspace working
          </p>
          <h2
            className="mt-2 font-display text-xl font-semibold tracking-[-0.025em] text-foreground"
            id="activation-heading"
          >
            {complete} of {steps.length} steps complete
          </h2>
          <div
            aria-hidden="true"
            className="mt-3.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-inset"
          >
            <span
              className="block h-full rounded-full bg-gradient-to-r from-primary to-accent transition-[width]"
              style={{ width: `${percent}%` }}
            />
          </div>
          <p className="mt-3 text-sm leading-6 text-muted">
            Each step runs on your own data and waits for your decision before
            it changes anything. Nothing is added to your career record without
            you.
          </p>
          {unknown && (
            <Badge className="mt-3" tone="warning">
              Some step states could not be loaded
            </Badge>
          )}
        </header>

        <ol className="space-y-0">
          {steps.map(({ action, description, id, label, state }, index) => {
            const visual = stateVisual[state];
            const Icon = visual.icon;
            return (
              <li className="relative flex gap-4 pb-6 last:pb-0" key={id}>
                {index < steps.length - 1 && (
                  <span
                    aria-hidden="true"
                    className={cn(
                      "absolute left-[0.9375rem] top-8 bottom-0 w-px",
                      state === "done" ? "bg-success/40" : "bg-line",
                    )}
                  />
                )}
                <span
                  className={cn(
                    "relative z-10 mt-0.5 grid size-8 shrink-0 place-items-center rounded-full border",
                    visual.className,
                  )}
                >
                  <Icon aria-hidden="true" className="size-4" />
                </span>
                <div className="min-w-0 flex-1 pt-0.5">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <h3
                      className={cn(
                        "text-sm font-semibold",
                        state === "pending"
                          ? "text-muted-strong"
                          : "text-foreground",
                      )}
                    >
                      {label}
                    </h3>
                    <span className="text-xs font-bold uppercase tracking-[0.06em] text-muted">
                      {visual.label}
                    </span>
                  </div>
                  <p className="mt-1 max-w-2xl text-xs leading-5 text-muted">
                    {description}
                  </p>
                  {action && state !== "pending" && (
                    <Link
                      className={cn(
                        buttonStyles.base,
                        state === "current"
                          ? buttonStyles.primary
                          : buttonStyles.secondary,
                        "mt-3 min-h-9 px-3 text-xs",
                      )}
                      href={action.href}
                    >
                      {action.label}
                      <ArrowRight aria-hidden="true" className="size-3.5" />
                    </Link>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}

const gatePreview = [
  {
    description:
      "Your PDF or DOCX is scanned for malware in an isolated worker, then parsed into structured fields with the source location of each one.",
    icon: FileSearch,
    label: "Screen and parse",
  },
  {
    description:
      "You confirm or correct anything the parser was unsure about. Nothing uncertain becomes a career fact without you.",
    icon: UserRoundCheck,
    label: "You confirm",
  },
  {
    description:
      "Approved facts populate your experiences, skills, and evidence, each one traceable back to where it came from.",
    icon: BadgeCheck,
    label: "Your record builds",
  },
  {
    description:
      "Your health report, role comparisons, opportunity tracking, and interview preparation all switch on from that record.",
    icon: LockKeyhole,
    label: "The workspace activates",
  },
] as const;

/**
 * The workspace is gated only when there is genuinely nothing to show: no
 * document and no career record. An account that typed its record by hand keeps
 * the full workspace.
 */
export function shouldGateWorkspace(
  resumeHealth: DashboardResumeHealth,
  summary: DashboardSummary,
): boolean {
  return (
    resumeHealth.kind === "empty" &&
    summary.record.experiences.kind === "count" &&
    summary.record.experiences.value === 0
  );
}

export function ActivationGate({ displayName }: { displayName: string }) {
  return (
    <main
      className="workspace-page grid place-items-center pb-16"
      id="main-content"
    >
      <div className="w-full max-w-3xl">
        <section
          aria-labelledby="activation-gate-heading"
          className="workspace-hero px-5 py-7 shadow-[var(--shadow-lg)] sm:px-9 sm:py-10"
        >
          <div className="flex flex-col items-center text-center">
            <span className="grid size-14 place-items-center rounded-[var(--radius-card)] bg-primary text-white shadow-[var(--shadow-md)]">
              <UploadCloud aria-hidden="true" className="size-7" />
            </span>
            <p className="eyebrow mt-5">Welcome, {displayName}</p>
            <h1
              className="balanced mt-2 font-display text-[clamp(1.6rem,2.8vw,2.15rem)] font-semibold leading-[1.14] tracking-[-0.035em] text-foreground"
              id="activation-gate-heading"
            >
              Add your resume to activate your workspace.
            </h1>
            <p className="balanced mt-3 max-w-xl text-sm leading-6 text-muted sm:text-[0.9375rem]">
              Rezumi builds everything downstream from one reviewed source of
              truth. Until a resume or a career record exists, there is nothing
              honest to show you here.
            </p>
            <div className="mt-6 flex w-full flex-col items-center gap-3 sm:w-auto sm:flex-row">
              <Link
                className={cn(
                  buttonStyles.base,
                  buttonStyles.primary,
                  "w-full sm:w-auto",
                )}
                href="/resume-health/account"
              >
                Upload your resume
                <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
              <Link
                className={cn(
                  buttonStyles.base,
                  buttonStyles.secondary,
                  "w-full sm:w-auto",
                )}
                href="/career-profile"
              >
                Build it manually instead
              </Link>
            </div>
            <p className="mt-4 flex items-center gap-1.5 text-xs text-muted">
              <ShieldCheck aria-hidden="true" className="size-3.5" />
              PDF or DOCX. Private to your account, and deletable at any time.
            </p>
          </div>

          <ol className="mt-8 grid gap-3 border-t border-line pt-7 sm:grid-cols-2">
            {gatePreview.map(({ description, icon: Icon, label }, index) => (
              <li
                className="rounded-[var(--radius-card)] border border-line bg-surface/80 p-4"
                key={label}
              >
                <div className="flex items-center gap-2.5">
                  <span className="grid size-8 shrink-0 place-items-center rounded-[var(--radius-small)] bg-primary-soft text-primary-strong">
                    <Icon aria-hidden="true" className="size-4" />
                  </span>
                  <span className="text-xs font-bold uppercase tracking-[0.06em] text-muted">
                    Step {index + 1}
                  </span>
                </div>
                <h2 className="mt-2.5 text-sm font-semibold text-foreground">
                  {label}
                </h2>
                <p className="mt-1 text-xs leading-5 text-muted">
                  {description}
                </p>
              </li>
            ))}
          </ol>
        </section>

        <p className="mt-4 text-center text-xs leading-5 text-muted">
          Rezumi never invents an employer, title, date, or number. Measurements
          shown after activation are internal, explainable signals&mdash;never
          an employer or applicant-tracking-system score.
        </p>
      </div>
    </main>
  );
}
