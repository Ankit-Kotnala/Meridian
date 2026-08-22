"use client";

import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock3,
  FileWarning,
  Info,
  Lightbulb,
  LogIn,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";

import {
  Alert,
  Badge,
  Button,
  Card,
  CheckboxField,
  ConfirmDialog,
  ErrorState,
  LoadingSkeleton,
  ScoreBar,
  ScoreRing,
  Tabs,
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
  "Rezumi scores are internal readiness measurements. They are not scores provided by an employer or applicant tracking system and do not guarantee interviews or employment outcomes.";

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

function NumberedSuggestionList({
  findings,
}: {
  findings: ResumeFinding[];
}) {
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
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground">
              {finding.title}
            </p>
            <p className="mt-1 text-xs leading-5 text-muted">
              {finding.description}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function FindingList({ findings }: { findings: ResumeFinding[] }) {
  if (findings.length === 0) {
    return (
      <p className="rounded-xl bg-surface-subtle p-4 text-sm text-muted">
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
              <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-surface-subtle">
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
    <div className="grid gap-5 py-5 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,0.85fr)]">
      <div className="workspace-panel">
        <div className="border-b border-line px-4 py-3.5 sm:px-5">
          <h2 className="text-sm font-bold text-foreground">Score breakdown</h2>
          <p className="mt-0.5 text-xs text-muted">
            Versioned component contributions
          </p>
        </div>
        <div className="space-y-5 p-4 sm:p-5">
          {report.components.length > 0 ? (
            report.components.map((component) => (
              <div key={component.key}>
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
                <p className="mt-2 text-xs leading-5 text-muted">
                  {component.explanation}
                </p>
                <details className="mt-3 rounded-[var(--radius-control)] border border-line bg-surface-subtle/70 p-3">
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
      </div>
      <div className="workspace-panel">
        <div className="border-b border-line px-4 py-3.5 sm:px-5">
          <h2 className="text-sm font-bold text-foreground">Suggested changes</h2>
          <p className="mt-0.5 text-xs text-muted">Prioritized actions</p>
        </div>
        <div className="p-4 sm:p-5">
          <FindingList findings={quickWins} />
        </div>
      </div>
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
          <div className="rounded-xl bg-surface-subtle p-4">
            <dt className="font-bold text-muted">Engine version</dt>
            <dd className="mt-1 break-all font-mono text-xs text-foreground">
              {report.engineVersion}
            </dd>
          </div>
          <div className="rounded-xl bg-surface-subtle p-4">
            <dt className="font-bold text-muted">Configuration version</dt>
            <dd className="mt-1 break-all font-mono text-xs text-foreground">
              {report.configurationVersion}
            </dd>
          </div>
          <div className="rounded-xl bg-surface-subtle p-4">
            <dt className="font-bold text-muted">Feature schema version</dt>
            <dd className="mt-1 break-all font-mono text-xs text-foreground">
              {report.featureSchemaVersion}
            </dd>
          </div>
          <div className="rounded-xl bg-surface-subtle p-4">
            <dt className="font-bold text-muted">Feature-set hash</dt>
            <dd className="mt-1 break-all font-mono text-xs text-foreground">
              {report.featureSetHash}
            </dd>
          </div>
          <div className="rounded-xl bg-surface-subtle p-4 sm:col-span-2">
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
                  className="flex items-baseline justify-between gap-4 rounded-lg bg-surface-subtle px-3 py-2 text-xs"
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
          ? "workspace-page space-y-5"
          : "site-container py-8 sm:py-12"
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
        <Button onClick={() => setDeleteOpen(true)} variant="ghost">
          <Trash2 aria-hidden="true" className="size-4" /> Delete resume
        </Button>
      </header>

      {deleteFailure && (
        <Alert className="mb-5" title="Resume not deleted" tone="danger">
          {deleteFailure}
        </Alert>
      )}

      <div
        className={
          access === "account"
            ? "grid gap-5 lg:grid-cols-[minmax(0,1.65fr)_minmax(16rem,0.9fr)]"
            : undefined
        }
      >
      <section className="workspace-panel min-w-0 overflow-hidden">
        <div className="grid gap-6 p-5 sm:p-6 lg:grid-cols-[auto_minmax(0,1fr)] lg:items-start">
          <div className="flex flex-col items-center">
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
                size="lg"
                tone={scoreTone}
              />
            )}
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap gap-2">
              <Badge tone={scoreTone === "primary" ? "primary" : scoreTone}>
                {scoreLabel}
              </Badge>
              {report.status !== "insufficientData" && (
                <Badge tone="success">Well structured</Badge>
              )}
              {report.warnings.length > 0 && (
                <Badge tone="warning">Needs improvement</Badge>
              )}
            </div>
            <h2
              className="mt-3 truncate text-base font-bold text-foreground"
              title={document?.displayFilename}
            >
              {document?.displayFilename ?? "Resume document"}
            </h2>
            <p className="mt-1 text-xs text-muted">
              {document ? `Updated ${date(document.updatedAt)}` : null}
            </p>
            <div className="mt-3 flex items-center gap-2">
              <ShieldCheck aria-hidden="true" className="size-4 text-primary" />
              <span className="text-sm font-semibold text-foreground">
                Internal Rezumi measure
              </span>
            </div>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
              {SCORE_DISCLAIMER}
            </p>
            {report.status === "insufficientData" && (
              <Alert
                className="mt-4"
                title="Not enough reliable data"
                tone="warning"
              >
                Rezumi did not turn missing or uncertain information into a
                deceptively precise score. Review the warnings and parsed
                content.
              </Alert>
            )}
          </div>
        </div>

        {report.components.length > 0 && (
          <div className="report-component-grid">
            {report.components.slice(0, 4).map((component) => (
              <div className="report-component-cell" key={component.key}>
                <ScoreRing
                  label={`${component.label} score`}
                  score={component.score}
                  size="sm"
                  tone={
                    component.score >= 80
                      ? "success"
                      : component.score >= 65
                        ? "warning"
                        : "primary"
                  }
                />
                <p className="mt-3 text-xs font-semibold text-muted">
                  {component.label}
                </p>
                <p className="mt-1 text-sm font-bold tabular-nums text-foreground">
                  {component.score}
                  <span className="text-xs font-semibold text-muted">/100</span>
                </p>
                <p className="mt-2 text-[0.6875rem] leading-4 text-muted">
                  {component.explanation}
                </p>
              </div>
            ))}
          </div>
        )}

        {access === "account" && report.components.length > 0 && (
          <div className="space-y-5 border-t border-line p-4 sm:p-5">
            {report.components.map((component) => (
              <div key={`detail-${component.key}`}>
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
                <details className="mt-3 rounded-[var(--radius-control)] border border-line bg-surface-subtle/70 p-3">
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
            ))}
          </div>
        )}
      </section>

      {access === "account" && (
        <aside className="workspace-panel min-w-0">
          <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3.5 sm:px-5">
            <h2 className="text-sm font-bold text-foreground">
              Suggested changes
            </h2>
          </div>
          <div className="p-4 sm:p-5">
            <NumberedSuggestionList findings={quickWins} />
          </div>
        </aside>
      )}
      </div>

      <Tabs
        className="mt-2"
        label="Resume Health report sections"
        tabs={
          access === "account"
            ? [
                { id: "findings", label: "All findings", panel: findingsPanel },
                {
                  id: "methodology",
                  label: "Methodology",
                  panel: methodologyPanel,
                },
              ]
            : [
                { id: "overview", label: "Overview", panel: overviewPanel },
                { id: "findings", label: "All findings", panel: findingsPanel },
                {
                  id: "methodology",
                  label: "Methodology",
                  panel: methodologyPanel,
                },
              ]
        }
      />

      {access === "account" && report && autoImport && (
        <div className="mt-5 space-y-3">
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
