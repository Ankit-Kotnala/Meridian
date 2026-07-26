"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileDiff,
  FileWarning,
  Info,
  Lightbulb,
  LogIn,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  CheckboxField,
  ConfirmDialog,
  ErrorState,
  LoadingSkeleton,
  ScoreBar,
  ScoreRing,
  Tabs,
  buttonStyles,
  cn,
} from "@careeros/ui";

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
  "CareerOS scores are internal readiness measurements. They are not scores provided by an employer or applicant tracking system and do not guarantee interviews or employment outcomes.";

const severityPresentation = {
  info: { icon: Info, label: "Information", tone: "primary" as const },
  opportunity: {
    icon: Lightbulb,
    label: "Opportunity",
    tone: "success" as const,
  },
  warning: {
    icon: AlertTriangle,
    label: "Warning",
    tone: "warning" as const,
  },
  critical: {
    icon: FileWarning,
    label: "Critical",
    tone: "danger" as const,
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

function FindingList({ findings }: { findings: ResumeFinding[] }) {
  if (findings.length === 0) {
    return (
      <p className="rounded-xl bg-slate-50 p-4 text-sm text-muted">
        No findings were recorded in this category.
      </p>
    );
  }
  return (
    <ul className="space-y-3">
      {findings.map((finding) => {
        const presentation = severityPresentation[finding.severity];
        const Icon = presentation.icon;
        return (
          <li className="rounded-xl border border-line p-4" key={finding.id}>
            <div className="flex items-start gap-3">
              <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-slate-50">
                <Icon aria-hidden="true" className="size-4 text-foreground" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-extrabold text-foreground">
                    {finding.title}
                  </h3>
                  <Badge tone={presentation.tone}>{presentation.label}</Badge>
                  {finding.section && <Badge>{finding.section}</Badge>}
                </div>
                <p className="mt-2 text-sm leading-6 text-muted">
                  {finding.description}
                </p>
                {finding.action && (
                  <p className="mt-3 rounded-lg bg-primary-soft/45 p-3 text-xs font-semibold leading-5 text-primary-strong">
                    Next step: {finding.action}
                  </p>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function ResumeHealthReportView({
  access,
  analysisId,
}: {
  access: ResumeHealthAccess;
  analysisId: string;
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

  const scoreTone =
    report.scoreBand === "strong"
      ? ("success" as const)
      : report.scoreBand === "developing" ||
          report.scoreBand === "needsAttention"
        ? ("warning" as const)
        : ("primary" as const);
  const scoreLabel =
    report.scoreBand === "strong"
      ? "Strong"
      : report.scoreBand === "developing"
        ? "Developing"
        : report.scoreBand === "needsAttention"
          ? "Needs attention"
          : "Not scored";
  const issues = report.findings.filter(
    (finding) => finding.category === "issue",
  );
  const quickWins = report.findings.filter(
    (finding) => finding.category === "quick_win",
  );
  const sectionFeedback = report.findings.filter(
    (finding) => finding.category === "section_feedback",
  );

  const overviewPanel = (
    <div className="grid gap-5 py-5 lg:grid-cols-[1.1fr_0.9fr]">
      <Card>
        <CardHeader
          description="Versioned component contributions"
          title="Score breakdown"
        />
        <div className="space-y-5 p-5 sm:p-6">
          {report.components.length > 0 ? (
            report.components.map((component) => (
              <div key={component.key}>
                <ScoreBar
                  label={`${component.label} (${component.weight}% weight)`}
                  score={component.score}
                  tone="primary"
                />
                <p className="mt-2 text-xs leading-5 text-muted">
                  {component.explanation}
                </p>
                <details className="mt-3 rounded-xl border border-line bg-slate-50/70 p-3">
                  <summary className="cursor-pointer rounded-md text-xs font-bold text-foreground outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2">
                    How {component.label} was calculated
                  </summary>
                  <p className="mt-3 text-xs leading-5 text-muted">
                    This component contributed exactly{" "}
                    {fixedPoint(component.rawContributionBasisPoints)} points to
                    the overall score. Its measured inputs were:
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
                </details>
              </div>
            ))
          ) : (
            <p className="text-sm leading-6 text-muted">
              Reliable component scores were not available for this document.
            </p>
          )}
        </div>
      </Card>
      <Card>
        <CardHeader description="Prioritized actions" title="Quick wins" />
        <div className="p-5">
          <FindingList findings={quickWins} />
        </div>
      </Card>
    </div>
  );

  const findingsPanel = (
    <div className="grid gap-5 py-5 lg:grid-cols-2">
      <Card className="p-5">
        <h2 className="mb-4 text-sm font-extrabold">Issues</h2>
        <FindingList findings={issues} />
      </Card>
      <Card className="p-5">
        <h2 className="mb-4 text-sm font-extrabold">Section feedback</h2>
        <FindingList findings={sectionFeedback} />
      </Card>
    </div>
  );

  const methodologyPanel = (
    <div className="py-5">
      <Card className="p-5 sm:p-6">
        <h2 className="text-sm font-extrabold">
          How this report was calculated
        </h2>
        <p className="mt-3 text-sm leading-6 text-muted">{SCORE_DISCLAIMER}</p>
        <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2">
          <div className="rounded-xl bg-slate-50 p-4">
            <dt className="font-bold text-muted">Engine version</dt>
            <dd className="mt-1 break-all font-mono text-xs text-foreground">
              {report.engineVersion}
            </dd>
          </div>
          <div className="rounded-xl bg-slate-50 p-4">
            <dt className="font-bold text-muted">Configuration version</dt>
            <dd className="mt-1 break-all font-mono text-xs text-foreground">
              {report.configurationVersion}
            </dd>
          </div>
          <div className="rounded-xl bg-slate-50 p-4">
            <dt className="font-bold text-muted">Feature schema version</dt>
            <dd className="mt-1 break-all font-mono text-xs text-foreground">
              {report.featureSchemaVersion}
            </dd>
          </div>
          <div className="rounded-xl bg-slate-50 p-4">
            <dt className="font-bold text-muted">Feature-set hash</dt>
            <dd className="mt-1 break-all font-mono text-xs text-foreground">
              {report.featureSetHash}
            </dd>
          </div>
          <div className="rounded-xl bg-slate-50 p-4 sm:col-span-2">
            <dt className="font-bold text-muted">Input snapshot</dt>
            <dd className="mt-1 text-xs leading-5 text-foreground">
              Reviewed canonical resume {report.canonicalResumeId}. Reanalysis
              creates a new result; this report is not recomputed in place.
            </dd>
          </div>
        </dl>
        <details className="mt-5 rounded-xl border border-line p-4">
          <summary className="cursor-pointer rounded-md text-sm font-extrabold text-foreground outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2">
            View measured input values
          </summary>
          <p className="mt-3 text-xs leading-5 text-muted">
            These deterministic observations came from the immutable reviewed
            snapshot. They describe document structure, not candidate quality.
          </p>
          {report.featureValues.length > 0 ? (
            <dl className="mt-3 grid gap-2 sm:grid-cols-2">
              {report.featureValues.map((feature) => (
                <div
                  className="flex items-baseline justify-between gap-4 rounded-lg bg-slate-50 px-3 py-2 text-xs"
                  key={feature.key}
                >
                  <dt className="font-semibold text-muted">{feature.label}</dt>
                  <dd className="font-bold text-foreground">
                    {feature.displayValue}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="mt-3 text-xs leading-5 text-muted">
              Measured input values are unavailable for this report.
            </p>
          )}
        </details>
      </Card>
    </div>
  );

  return (
    <main
      className={
        access === "account"
          ? "mx-auto max-w-6xl p-4 sm:p-6 lg:p-8"
          : "site-container py-8 sm:py-12"
      }
      id="main-content"
    >
      <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow">General document check</p>
          <h1 className="mt-2 text-2xl font-black tracking-[-0.035em] text-foreground sm:text-3xl">
            Resume Health report
          </h1>
          <p className="mt-2 text-sm text-muted">
            Calculated {date(report.computedAt)} from a reviewed immutable
            snapshot.
          </p>
        </div>
        <Button onClick={() => setDeleteOpen(true)} variant="ghost">
          <Trash2 aria-hidden="true" className="size-4" /> Delete resume
        </Button>
      </header>

      {deleteFailure && (
        <Alert className="mb-5" title="Resume not deleted" tone="danger">
          {deleteFailure}
        </Alert>
      )}

      <Card className="overflow-hidden">
        <div className="grid gap-6 p-5 sm:p-7 lg:grid-cols-[13rem_1fr] lg:items-center">
          <div className="flex flex-col items-center rounded-2xl bg-slate-50 p-5 text-center">
            {report.score === null ? (
              <span className="grid size-32 place-items-center rounded-full border-8 border-slate-200 text-center text-sm font-black text-muted">
                Score
                <br /> unavailable
              </span>
            ) : (
              <ScoreRing
                label="Resume Health Score"
                score={report.score}
                size="lg"
                tone={scoreTone}
              />
            )}
            <Badge
              className="mt-4"
              tone={scoreTone === "primary" ? "primary" : scoreTone}
            >
              {scoreLabel}
            </Badge>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck aria-hidden="true" className="size-5 text-primary" />
              <h2 className="font-extrabold text-foreground">
                Internal CareerOS measure
              </h2>
            </div>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
              {SCORE_DISCLAIMER}
            </p>
            {report.status === "insufficientData" && (
              <Alert
                className="mt-4"
                title="Not enough reliable data"
                tone="warning"
              >
                CareerOS did not turn missing or uncertain information into a
                deceptively precise score. Review the warnings and parsed
                content.
              </Alert>
            )}
            {report.warnings.length > 0 && (
              <ul className="mt-4 space-y-2 text-xs leading-5 text-muted">
                {report.warnings.map((warning) => (
                  <li className="flex items-start gap-2" key={warning}>
                    <AlertTriangle
                      aria-hidden="true"
                      className="mt-0.5 size-3.5 shrink-0 text-warning-strong"
                    />
                    {warning}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </Card>

      <Tabs
        className="mt-6"
        label="Resume Health report sections"
        tabs={[
          { id: "overview", label: "Overview", panel: overviewPanel },
          { id: "findings", label: "All findings", panel: findingsPanel },
          { id: "methodology", label: "Methodology", panel: methodologyPanel },
        ]}
      />

      {access === "account" && (
        <Card className="mt-5 flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
          <div className="flex items-start gap-3">
            <FileDiff
              aria-hidden="true"
              className="mt-0.5 size-5 shrink-0 text-primary"
            />
            <div>
              <h2 className="font-extrabold">
                Propose reviewed Career Record facts
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
                Create pending proposals from the typed fields you reviewed.
                Your Career Record is unchanged until you accept each proposal.
              </p>
            </div>
          </div>
          <Link
            className={cn(buttonStyles.base, buttonStyles.primary)}
            href={`/career-profile/imports?documentId=${encodeURIComponent(report.documentId)}&snapshotId=${encodeURIComponent(report.canonicalResumeId)}`}
          >
            Review import proposals
          </Link>
        </Card>
      )}

      {access === "guest" && document && (
        <Card className="mt-5 p-5 sm:p-6">
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
