"use client";

import {
  ArrowLeft,
  CheckCircle2,
  Clock3,
  LogIn,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";

import {
  Alert,
  Button,
  Card,
  CheckboxField,
  ConfirmDialog,
  ErrorState,
  LoadingSkeleton,
  ScoreBar,
  ScoreRing,
  buttonStyles,
  cn,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  ApiRequestError,
  claimGuestDocument,
  deleteDocument,
  getDocument,
  getResumeHealthReport,
} from "../api/resume-health-api";
import type {
  DocumentDetail,
  ResumeFinding,
  ResumeHealthAccess,
  ResumeHealthReport,
} from "../api/types";

export const SCORE_DISCLAIMER =
  "Meridian scores are internal readiness measurements. They are not scores provided by an employer or applicant tracking system and do not guarantee interviews or employment outcomes.";

const scoreBandStyle = {
  strong: {
    tone: "success" as const,
    tint: "var(--success)",
    tintStrong: "var(--success-strong)",
    label: "Strong",
  },
  developing: {
    tone: "warning" as const,
    tint: "var(--warning-visual)",
    tintStrong: "var(--warning-strong)",
    label: "Developing",
  },
  needsAttention: {
    tone: "warning" as const,
    tint: "var(--danger)",
    tintStrong: "var(--danger-strong)",
    label: "Needs attention",
  },
};

function date(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function fixedPoint(value: number): string {
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
  }).format(value / 100);
}

function verdictSentence(
  report: ResumeHealthReport,
  quickWinCount: number,
): string {
  if (report.score === null) {
    return "There wasn’t enough reliable text to calculate a dependable score.";
  }
  const band = report.scoreBand
    ? scoreBandStyle[report.scoreBand].label
    : "Reviewed";
  if (band === "Strong") {
    return quickWinCount > 0
      ? `Strong — this reads clearly. ${quickWinCount} small ${quickWinCount === 1 ? "tweak" : "tweaks"} would make it sharper.`
      : "Strong — this resume reads clearly against Meridian’s structural checks.";
  }
  if (band === "Developing") {
    return quickWinCount > 0
      ? `Developing — a solid foundation. ${quickWinCount} focused ${quickWinCount === 1 ? "change" : "changes"} would move this forward.`
      : "Developing — a solid foundation with room to sharpen.";
  }
  return quickWinCount > 0
    ? `Needs attention — ${quickWinCount} fix${quickWinCount === 1 ? "" : "es"} below would meaningfully improve how this reads.`
    : "Needs attention — review the findings below before sending this out.";
}

function ComponentBreakdown({
  components,
}: {
  components: ResumeHealthReport["components"];
}) {
  if (components.length === 0) {
    return (
      <p className="text-sm leading-6 text-muted">
        Reliable component scores were not available for this document.
      </p>
    );
  }
  return (
    <div>
      {components.map((component) => (
        <div className="health-breakdown-row" key={component.key}>
          <ScoreBar
            label={`${component.label} (${component.weight}% weight)`}
            score={component.score}
            tone={
              component.score >= 80
                ? "success"
                : component.score >= 65
                  ? "warning"
                  : "primary"
            }
          />
          <p className="mt-2.5 text-xs leading-5 text-muted">
            {component.explanation}
          </p>
          <details className="group mt-2.5">
            <summary className="inline-flex cursor-pointer items-center gap-1 rounded-md text-xs font-bold text-primary outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2">
              How {component.label} was calculated
            </summary>
            <div className="mt-3 rounded-[var(--radius-control)] bg-surface-subtle p-3.5">
              <p className="text-xs leading-5 text-muted">
                This component contributed exactly{" "}
                {fixedPoint(component.rawContributionBasisPoints)} points to the
                overall score. Its measured inputs were:
              </p>
              {component.featureContributions.length > 0 ? (
                <dl
                  aria-label={`${component.label} feature contributions`}
                  className="mt-3 divide-y divide-line"
                >
                  {component.featureContributions.map((feature) => (
                    <div
                      className="grid gap-1 py-2 text-xs sm:grid-cols-[1fr_auto] sm:gap-4"
                      key={feature.key}
                    >
                      <dt className="font-semibold text-foreground">
                        {feature.label}
                      </dt>
                      <dd className="text-muted sm:text-right">
                        {fixedPoint(feature.rawScoreBasisPoints)}% times{" "}
                        {fixedPoint(feature.rawWeightBasisPoints)}% ={" "}
                        {fixedPoint(feature.rawContributionBasisPoints)}{" "}
                        component points
                      </dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="mt-3 text-xs leading-5 text-muted">
                  Feature contribution details are unavailable for this
                  component.
                </p>
              )}
            </div>
          </details>
        </div>
      ))}
    </div>
  );
}

function FixTheseFirst({ findings }: { findings: ResumeFinding[] }) {
  if (findings.length === 0) {
    return (
      <p className="text-sm text-muted">
        No prioritized suggestions were recorded for this report.
      </p>
    );
  }

  return (
    <ul className="suggestion-list">
      {findings.slice(0, 4).map((finding) => (
        <li className="suggestion-item" key={finding.id}>
          <div className="min-w-0 pt-0.5">
            <p className="text-sm font-bold text-foreground">{finding.title}</p>
            <p className="mt-1 text-xs leading-5 text-muted">
              {finding.description}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function MeasuredInputs({
  featureValues,
}: {
  featureValues: ResumeHealthReport["featureValues"];
}) {
  if (featureValues.length === 0) {
    return (
      <p className="text-sm leading-6 text-muted">
        Measured input values are unavailable for this report.
      </p>
    );
  }
  return (
    <dl className="grid gap-2 sm:grid-cols-2">
      {featureValues.map((feature) => (
        <div
          className="flex items-baseline justify-between gap-4 rounded-lg bg-surface-subtle px-3 py-2 text-xs"
          key={feature.key}
        >
          <dt className="font-semibold text-muted">{feature.label}</dt>
          <dd className="font-bold text-foreground">{feature.displayValue}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ResumeHealthReportView({
  access,
  analysisId,
  autoImport,
}: {
  access: ResumeHealthAccess;
  analysisId: string;
  autoImport?: ReactNode;
}) {
  const router = useRouter();
  const [report, setReport] = useState<ResumeHealthReport>();
  const [document, setDocument] = useState<DocumentDetail>();
  const [failure, setFailure] = useState<string>();
  const [expired, setExpired] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteFailure, setDeleteFailure] = useState<string>();
  const [claimConsent, setClaimConsent] = useState(false);
  const [claiming, setClaiming] = useState(false);
  const [claimFailure, setClaimFailure] = useState<string>();
  const [signInRequired, setSignInRequired] = useState(false);

  const load = useCallback(async () => {
    setFailure(undefined);
    setExpired(false);
    try {
      const nextReport = await getResumeHealthReport(access, analysisId);
      const nextDocument = await getDocument(access, nextReport.documentId);
      setReport(nextReport);
      setDocument(nextDocument);
    } catch (error) {
      if (
        error instanceof ApiRequestError &&
        new Set([404, 410]).has(error.failure.status)
      ) {
        setExpired(access === "guest");
      }
      setFailure(
        requestErrorMessage(
          error,
          "We couldn’t load this Resume Health report.",
        ),
      );
    }
  }, [access, analysisId]);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  async function remove() {
    if (!document) return;
    setDeleting(true);
    setDeleteFailure(undefined);
    try {
      const accepted = await deleteDocument(
        access,
        document.id,
        document.version,
      );
      setDeleteOpen(false);
      const prefix =
        access === "account"
          ? "/resume-health/account"
          : "/resume-health/guest";
      router.replace(
        `${prefix}/processing/${encodeURIComponent(accepted.job.id)}`,
      );
    } catch (error) {
      setDeleteFailure(
        requestErrorMessage(
          error,
          "We couldn’t delete this resume. Reload and try again.",
        ),
      );
    } finally {
      setDeleting(false);
    }
  }

  async function claim() {
    if (!document || !claimConsent) return;
    setClaiming(true);
    setClaimFailure(undefined);
    setSignInRequired(false);
    try {
      await claimGuestDocument(document.id);
      router.replace("/resume-health/account");
      router.refresh();
    } catch (error) {
      if (error instanceof ApiRequestError && error.failure.status === 401) {
        setSignInRequired(true);
        setClaimFailure(
          "Sign in to a verified account, then return here to explicitly save this guest resume.",
        );
      } else {
        setClaimFailure(
          requestErrorMessage(error, "We couldn’t save this guest resume."),
        );
      }
    } finally {
      setClaiming(false);
    }
  }

  if (!report && !failure) {
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <LoadingSkeleton />
      </main>
    );
  }
  if (!report) {
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={
            expired
              ? "This short-lived guest report has expired or was deleted. Its capability can no longer access the document."
              : (failure ?? "The report is unavailable.")
          }
          {...(!expired ? { onRetry: load } : {})}
          title={expired ? "Guest report expired" : "Report unavailable"}
        />
      </main>
    );
  }

  const band = report.scoreBand ? scoreBandStyle[report.scoreBand] : null;
  const scoreTone = band?.tone ?? "primary";
  const scoreLabel = band?.label ?? "Not scored";
  const quickWins = report.findings.filter(
    (finding) => finding.category === "quick_win",
  );

  return (
    <main
      className={
        access === "account"
          ? "workspace-page space-y-6"
          : "site-container space-y-6 py-8 sm:py-12"
      }
      id="main-content"
    >
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          {access === "account" && (
            <Link
              className="mb-3 inline-flex items-center gap-1.5 text-sm font-semibold text-primary-strong hover:underline"
              href="/resume-health/account"
            >
              <ArrowLeft aria-hidden="true" className="size-4" />
              Resume Health
            </Link>
          )}
          {access !== "account" && (
            <p className="eyebrow">General document check</p>
          )}
          <h1 className="font-display text-2xl font-bold tracking-[-0.03em] text-foreground sm:text-3xl">
            {access === "account" ? "Resume Health" : "Resume Health report"}
          </h1>
          <p className="mt-2 text-sm text-muted">
            Calculated {date(report.computedAt)} from a reviewed immutable
            snapshot.
          </p>
        </div>
        <Button
          aria-label="Delete resume"
          onClick={() => setDeleteOpen(true)}
          variant="ghost"
        >
          <Trash2 aria-hidden="true" className="size-4" /> Delete
        </Button>
      </header>

      {deleteFailure && (
        <Alert title="Resume not deleted" tone="danger">
          {deleteFailure}
        </Alert>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.65fr)_minmax(16rem,0.9fr)]">
        <div className="flex min-w-0 flex-col gap-5">
          <section
            className="health-hero min-w-0"
            style={
              {
                "--health-tint": band?.tint ?? "var(--primary)",
                "--health-tint-strong":
                  band?.tintStrong ?? "var(--primary-strong)",
              } as CSSProperties
            }
          >
            <span aria-hidden="true" className="health-hero-rule" />
            <div className="grid gap-6 p-5 pl-6 sm:p-7 sm:pl-8 lg:grid-cols-[auto_minmax(0,1fr)] lg:items-center">
              <div className="flex flex-col items-center gap-2">
                {report.score === null ? (
                  <span className="grid size-32 place-items-center rounded-full border-[10px] border-line text-center text-sm font-bold text-muted">
                    Score
                    <br /> unavailable
                  </span>
                ) : (
                  <ScoreRing
                    bandLabel={scoreLabel}
                    label="Resume Health Score"
                    score={report.score}
                    size="xl"
                    tone={scoreTone}
                  />
                )}
              </div>
              <div className="min-w-0">
                <span className="health-score-tag">
                  <ShieldCheck aria-hidden="true" className="size-3.5" />
                  Internal Meridian measure
                </span>
                <p className="health-verdict mt-3 max-w-xl">
                  {verdictSentence(report, quickWins.length)}
                </p>
                <h2
                  className="mt-3 truncate text-sm font-semibold text-muted-strong"
                  title={document?.displayFilename}
                >
                  {document?.displayFilename ?? "Resume document"}
                  {document ? ` · updated ${date(document.updatedAt)}` : null}
                </h2>
                {report.status === "insufficientData" && (
                  <Alert
                    className="mt-4"
                    title="Not enough reliable data"
                    tone="warning"
                  >
                    Meridian did not turn missing or uncertain information into
                    a deceptively precise score. Review the warnings and parsed
                    content.
                  </Alert>
                )}
              </div>
            </div>

            <p className="border-t border-line px-5 py-4 pl-6 text-xs leading-5 text-muted sm:px-7 sm:pl-8">
              {SCORE_DISCLAIMER}
            </p>
          </section>

          <div className="workspace-panel min-w-0">
            <div className="border-b border-line px-4 py-3.5 sm:px-5">
              <h2 className="text-sm font-bold text-foreground">
                What we measured
              </h2>
              <p className="mt-0.5 text-xs text-muted">
                Deterministic observations from the immutable reviewed snapshot.
                They describe document structure, not candidate quality.
              </p>
            </div>
            <div className="p-4 sm:p-5">
              <MeasuredInputs featureValues={report.featureValues} />
            </div>
          </div>
        </div>

        <div className="flex min-w-0 flex-col gap-5">
          <aside className="workspace-panel min-w-0">
            <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3.5 sm:px-5">
              <h2 className="text-sm font-bold text-foreground">
                Fix these first
              </h2>
            </div>
            <div className="p-4 sm:p-5">
              <FixTheseFirst findings={quickWins} />
            </div>
          </aside>

          <aside className="workspace-panel min-w-0">
            <div className="border-b border-line px-4 py-3.5 sm:px-5">
              <h2 className="text-sm font-bold text-foreground">
                Score breakdown
              </h2>
            </div>
            <div className="px-4 sm:px-5">
              <ComponentBreakdown components={report.components} />
            </div>
          </aside>
        </div>
      </div>

      {access === "account" && report && autoImport && (
        <div className="space-y-3">
          {autoImport}
          <p className="text-xs text-muted">
            Parsed experiences, skills, and contact details are added to your
            career record automatically. Anything ambiguous is in{" "}
            <Link
              className="text-link"
              href={`/career-profile/imports?documentId=${encodeURIComponent(report.documentId)}&snapshotId=${encodeURIComponent(document?.currentCanonicalResumeId ?? report.canonicalResumeId)}`}
            >
              resume import review
            </Link>
            .
          </p>
        </div>
      )}

      {access === "guest" && document && (
        <Card className="p-5 sm:p-6">
          <div className="flex items-start gap-3">
            <Clock3
              aria-hidden="true"
              className="mt-0.5 size-5 shrink-0 text-warning-strong"
            />
            <div className="min-w-0 flex-1">
              <h2 className="font-extrabold">
                Guest retention and optional save
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted">
                {report.expiresAt
                  ? `This guest document is scheduled to expire ${date(report.expiresAt)}.`
                  : "This guest document follows the short-retention policy shown at upload."}{" "}
                It is not part of an account unless you explicitly consent
                below.
              </p>
              <div className="mt-4 max-w-xl">
                <CheckboxField
                  checked={claimConsent}
                  description="This transfers the guest document and its current report into your signed-in account ownership."
                  id="guest-claim-consent"
                  label="Save this guest resume to my account"
                  onChange={(event) => setClaimConsent(event.target.checked)}
                />
              </div>
              {claimFailure && (
                <Alert className="mt-4" title="Resume not saved" tone="warning">
                  {claimFailure}
                </Alert>
              )}
              <div className="mt-4 flex flex-wrap gap-3">
                {signInRequired ? (
                  <Link
                    className={cn(buttonStyles.base, buttonStyles.primary)}
                    href={`/login?returnTo=${encodeURIComponent(`/resume-health/guest/report/${analysisId}`)}`}
                  >
                    <LogIn aria-hidden="true" className="size-4" /> Sign in and
                    return
                  </Link>
                ) : (
                  <Button
                    disabled={!claimConsent}
                    loading={claiming}
                    loadingLabel="Saving to account…"
                    onClick={() => void claim()}
                  >
                    <CheckCircle2 aria-hidden="true" className="size-4" /> Save
                    to my account
                  </Button>
                )}
              </div>
            </div>
          </div>
        </Card>
      )}

      <ConfirmDialog
        confirmLabel="Delete resume"
        description="This removes the private source, parsed data, active work, and report according to the deletion policy. This cannot be undone."
        loading={deleting}
        onConfirm={() => void remove()}
        onOpenChange={setDeleteOpen}
        open={deleteOpen}
        title="Delete this resume and report?"
      />
    </main>
  );
}
