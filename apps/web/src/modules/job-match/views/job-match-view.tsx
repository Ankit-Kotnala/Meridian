"use client";

import {
  BriefcaseBusiness,
  ClipboardCheck,
  FileDiff,
  Globe2,
  RefreshCcw,
  Search,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";

import {
  Alert,
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Input,
  LoadingSkeleton,
  PageHeader,
  ScoreBar,
  Select,
  buttonStyles,
  cn,
} from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  analyzeJob,
  createJob,
  deleteJob,
  getJobs,
  importJob,
  prioritizeOpportunity,
} from "../api/job-match-api";
import type {
  EmploymentType,
  Job,
  JobMatchAnalysis,
  JobSourceKind,
  OpportunityPriority,
  PreferenceFit,
  TailoringEffort,
  WorkModel,
} from "../api/types";

const sourceKinds: Array<{ label: string; value: JobSourceKind | "" }> = [
  { label: "Any source", value: "" },
  { label: "Pasted", value: "paste" },
  { label: "URL import", value: "url" },
  { label: "Manual", value: "manual" },
];

const workModels: Array<{ label: string; value: WorkModel }> = [
  { label: "Unknown", value: "unknown" },
  { label: "Remote", value: "remote" },
  { label: "Hybrid", value: "hybrid" },
  { label: "Onsite", value: "onsite" },
];

const employmentTypes: Array<{ label: string; value: EmploymentType }> = [
  { label: "Unknown", value: "unknown" },
  { label: "Full time", value: "full_time" },
  { label: "Part time", value: "part_time" },
  { label: "Contract", value: "contract" },
  { label: "Internship", value: "internship" },
  { label: "Temporary", value: "temporary" },
];

const preferenceFits: Array<{ label: string; value: PreferenceFit }> = [
  { label: "Unknown", value: "unknown" },
  { label: "Strong", value: "strong" },
  { label: "Acceptable", value: "acceptable" },
  { label: "Mismatch", value: "mismatch" },
];

const tailoringEfforts: Array<{ label: string; value: TailoringEffort }> = [
  { label: "Low", value: "low" },
  { label: "Medium", value: "medium" },
  { label: "High", value: "high" },
];

function humanize(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function scoreTone(score: number | null | undefined) {
  if (score === null || score === undefined) return "warning" as const;
  if (score >= 80) return "success" as const;
  if (score >= 60) return "primary" as const;
  return "warning" as const;
}

function stateTone(state: string) {
  if (state === "strong") return "success" as const;
  if (state === "missing" || state === "unknown") return "warning" as const;
  return "neutral" as const;
}

export function JobMatchView() {
  const [jobs, setJobs] = useState<Job[]>();
  const [activeJobId, setActiveJobId] = useState<string>();
  const [activeAnalysis, setActiveAnalysis] = useState<JobMatchAnalysis>();
  const [priority, setPriority] = useState<OpportunityPriority>();
  const [query, setQuery] = useState("");
  const [sourceKind, setSourceKind] = useState<JobSourceKind | "">("");
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [busyKey, setBusyKey] = useState<string>();

  const activeJob = useMemo(
    () => jobs?.find((job) => job.id === activeJobId) ?? activeAnalysis?.job,
    [activeAnalysis?.job, activeJobId, jobs],
  );

  const load = useCallback(async () => {
    setFailure(undefined);
    try {
      const page = await getJobs({ limit: 50 });
      setJobs(page.data);
      setActiveJobId((current) => current ?? page.data[0]?.id);
    } catch (error) {
      setFailure(requestErrorMessage(error, "Job Match could not be loaded."));
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  async function searchJobs(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyKey("search");
    setFailure(undefined);
    try {
      const page = await getJobs({
        limit: 50,
        q: query.trim(),
        sourceKind,
      });
      setJobs(page.data);
      setActiveJobId(page.data[0]?.id);
      setActiveAnalysis(undefined);
      setPriority(undefined);
    } catch (error) {
      setFailure(requestErrorMessage(error, "Job search failed."));
    } finally {
      setBusyKey(undefined);
    }
  }

  async function submitJob(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(event.currentTarget);
    const title = String(form.get("title") ?? "").trim();
    const sourceText = String(form.get("sourceText") ?? "").trim();
    setBusyKey("create");
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const job = await createJob({
        applicationDeadline: null,
        company: String(form.get("company") ?? "").trim() || null,
        compensation: String(form.get("compensation") ?? "").trim() || null,
        employmentType: String(form.get("employmentType")) as EmploymentType,
        location: String(form.get("location") ?? "").trim() || null,
        sourceKind: "paste",
        sourceText,
        sourceUrl: null,
        targetRoleId: null,
        title,
        workModel: String(form.get("workModel")) as WorkModel,
      });
      setJobs((current = []) => [
        job,
        ...current.filter((item) => item.id !== job.id),
      ]);
      setActiveJobId(job.id);
      setActiveAnalysis(undefined);
      setPriority(undefined);
      setSuccess(`${job.title} saved for matching.`);
      formElement.reset();
    } catch (error) {
      setFailure(requestErrorMessage(error, "The job could not be saved."));
    } finally {
      setBusyKey(undefined);
    }
  }

  async function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(event.currentTarget);
    const url = String(form.get("url") ?? "").trim();
    setBusyKey("import");
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const job = await importJob({ targetRoleId: null, url });
      setJobs((current = []) => [
        job,
        ...current.filter((item) => item.id !== job.id),
      ]);
      setActiveJobId(job.id);
      setActiveAnalysis(undefined);
      setPriority(undefined);
      setSuccess(`${job.title} imported.`);
      formElement.reset();
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "The job URL could not be imported."),
      );
    } finally {
      setBusyKey(undefined);
    }
  }

  async function runAnalysis(job: Job) {
    setBusyKey(`analyze-${job.id}`);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const analysis = await analyzeJob(job.id);
      setActiveAnalysis(analysis);
      setActiveJobId(job.id);
      setPriority(undefined);
      setSuccess(`${job.title} match analyzed.`);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "The job match could not be analyzed."),
      );
    } finally {
      setBusyKey(undefined);
    }
  }

  async function removeJob(job: Job) {
    setBusyKey(`delete-${job.id}`);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      await deleteJob(job);
      setJobs((current = []) => current.filter((item) => item.id !== job.id));
      if (activeJobId === job.id) {
        setActiveJobId(undefined);
        setActiveAnalysis(undefined);
        setPriority(undefined);
      }
      setSuccess(`${job.title} removed.`);
    } catch (error) {
      setFailure(requestErrorMessage(error, "The job could not be removed."));
    } finally {
      setBusyKey(undefined);
    }
  }

  async function submitPriority(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeJob || !activeAnalysis) return;
    const form = new FormData(event.currentTarget);
    setBusyKey("priority");
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const next = await prioritizeOpportunity(activeJob.id, {
        analysisId: activeAnalysis.id,
        careerDirectionFit: Number(form.get("careerDirectionFit")),
        compensationFit: String(form.get("compensationFit")) as PreferenceFit,
        existingContacts: Number(form.get("existingContacts")),
        locationFit: String(form.get("locationFit")) as PreferenceFit,
        tailoringEffort: String(form.get("tailoringEffort")) as TailoringEffort,
        userInterest: Number(form.get("userInterest")),
        workModelFit: String(form.get("workModelFit")) as PreferenceFit,
      });
      setPriority(next);
      setSuccess(`${activeJob.title} priority calculated.`);
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "Opportunity priority could not be calculated.",
        ),
      );
    } finally {
      setBusyKey(undefined);
    }
  }

  if (!jobs && failure) {
    return (
      <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={failure}
          onRetry={() => void load()}
          title="Job Match unavailable"
        />
      </main>
    );
  }

  if (!jobs) {
    return (
      <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
        <LoadingSkeleton />
      </main>
    );
  }

  return (
    <main
      className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8"
      id="main-content"
    >
      <div aria-live="polite" className="sr-only">
        {success || failure || ""}
      </div>

      <PageHeader
        actions={
          <Button onClick={() => void load()} variant="secondary">
            <RefreshCcw aria-hidden="true" className="size-4" />
            Refresh
          </Button>
        }
        description="Map one saved job’s explicit requirements to eligible career evidence. This job-specific measure is separate from general Resume Health and role readiness."
        eyebrow="Job Match"
        title="Application readiness"
      />

      {failure && (
        <Alert title="Job Match unavailable" tone="danger">
          {failure}
        </Alert>
      )}
      {success && (
        <Alert title="Saved" tone="success">
          {success}
        </Alert>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <section
          aria-labelledby="job-input-heading"
          className="rounded-lg border border-line bg-white p-4 shadow-sm"
        >
          <div className="flex items-center gap-2">
            <ClipboardCheck
              aria-hidden="true"
              className="size-5 text-primary"
            />
            <h2
              className="text-lg font-black text-foreground"
              id="job-input-heading"
            >
              Save a job posting
            </h2>
          </div>
          <form
            className="mt-4 grid gap-3 md:grid-cols-2"
            onSubmit={(event) => void submitJob(event)}
          >
            <label className="text-sm font-bold text-foreground">
              Job title
              <Input maxLength={200} name="title" required />
            </label>
            <label className="text-sm font-bold text-foreground">
              Company
              <Input maxLength={200} name="company" />
            </label>
            <label className="text-sm font-bold text-foreground">
              Location
              <Input maxLength={200} name="location" />
            </label>
            <label className="text-sm font-bold text-foreground">
              Compensation
              <Input maxLength={200} name="compensation" />
            </label>
            <label className="text-sm font-bold text-foreground">
              Work model
              <Select className="mt-1" defaultValue="unknown" name="workModel">
                {workModels.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </Select>
            </label>
            <label className="text-sm font-bold text-foreground">
              Employment type
              <Select
                className="mt-1"
                defaultValue="unknown"
                name="employmentType"
              >
                {employmentTypes.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </Select>
            </label>
            <label className="text-sm font-bold text-foreground md:col-span-2">
              Job description
              <textarea
                className="mt-1 min-h-56 w-full resize-y rounded-xl border border-line bg-white px-3.5 py-3 text-sm text-foreground shadow-sm outline-none placeholder:text-slate-400 focus:border-primary focus:ring-3 focus:ring-primary-soft"
                maxLength={50000}
                minLength={20}
                name="sourceText"
                required
              />
            </label>
            <div className="md:col-span-2">
              <Button loading={busyKey === "create"} type="submit">
                <ClipboardCheck aria-hidden="true" className="size-4" />
                Save job
              </Button>
            </div>
          </form>

          <form
            aria-labelledby="job-import-heading"
            className="mt-6 grid gap-3 border-t border-line pt-4 md:grid-cols-[minmax(0,1fr)_auto]"
            onSubmit={(event) => void submitImport(event)}
          >
            <label className="text-sm font-bold text-foreground">
              <span id="job-import-heading">Import from URL</span>
              <Input
                inputMode="url"
                maxLength={2048}
                name="url"
                placeholder="https://example.com/job"
                required
                type="url"
              />
            </label>
            <Button
              className="self-end"
              loading={busyKey === "import"}
              type="submit"
              variant="secondary"
            >
              <Globe2 aria-hidden="true" className="size-4" />
              Import
            </Button>
          </form>
        </section>

        <aside aria-labelledby="saved-jobs-heading" className="space-y-4">
          <form
            className="rounded-lg border border-line bg-white p-4 shadow-sm"
            onSubmit={(event) => void searchJobs(event)}
          >
            <h2
              className="text-lg font-black text-foreground"
              id="saved-jobs-heading"
            >
              Saved jobs
            </h2>
            <div className="mt-3 grid gap-3">
              <label className="text-sm font-bold text-foreground">
                Search
                <Input
                  maxLength={160}
                  onChange={(event) => setQuery(event.target.value)}
                  type="search"
                  value={query}
                />
              </label>
              <label className="text-sm font-bold text-foreground">
                Source
                <Select
                  className="mt-1"
                  onChange={(event) =>
                    setSourceKind(event.target.value as JobSourceKind | "")
                  }
                  value={sourceKind}
                >
                  {sourceKinds.map((item) => (
                    <option key={item.value || "any"} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </Select>
              </label>
              <Button
                loading={busyKey === "search"}
                type="submit"
                variant="secondary"
              >
                <Search aria-hidden="true" className="size-4" />
                Search
              </Button>
            </div>
          </form>

          {jobs.length === 0 ? (
            <EmptyState
              description="Saved job postings will appear here."
              title="No saved jobs"
            />
          ) : (
            <ul className="space-y-3">
              {jobs.map((job) => {
                const active = activeJob?.id === job.id;
                return (
                  <li
                    className={cn(
                      "rounded-lg border bg-white p-4 shadow-sm",
                      active ? "border-primary" : "border-line",
                    )}
                    key={job.id}
                  >
                    <button
                      aria-current={active ? "true" : undefined}
                      className="block w-full text-left"
                      onClick={() => {
                        setActiveJobId(job.id);
                        setActiveAnalysis(undefined);
                        setPriority(undefined);
                      }}
                      type="button"
                    >
                      <span className="block text-sm font-black text-foreground">
                        {job.title}
                      </span>
                      <span className="mt-1 block text-xs text-muted">
                        {[job.company, job.location]
                          .filter(Boolean)
                          .join(" / ") || humanize(job.sourceKind)}
                      </span>
                    </button>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge tone="neutral">{humanize(job.workModel)}</Badge>
                      <Badge tone="neutral">
                        {job.requirements.length} requirements
                      </Badge>
                    </div>
                    <div className="mt-3 flex gap-2">
                      <Button
                        className="flex-1"
                        loading={busyKey === `analyze-${job.id}`}
                        onClick={() => void runAnalysis(job)}
                        variant="secondary"
                      >
                        <BriefcaseBusiness
                          aria-hidden="true"
                          className="size-4"
                        />
                        Analyze
                      </Button>
                      <Button
                        aria-label={`Remove ${job.title}`}
                        loading={busyKey === `delete-${job.id}`}
                        onClick={() => void removeJob(job)}
                        variant="ghost"
                      >
                        <Trash2 aria-hidden="true" className="size-4" />
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </aside>
      </div>

      <section aria-labelledby="analysis-heading" className="space-y-4">
        <h2
          className="text-lg font-black text-foreground"
          id="analysis-heading"
        >
          Requirement matrix
        </h2>
        {!activeJob ? (
          <EmptyState
            description="Select or save a job to see extracted requirements."
            title="Choose a job"
          />
        ) : !activeAnalysis ? (
          <div className="rounded-lg border border-line bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h3 className="text-base font-black text-foreground">
                  {activeJob.title}
                </h3>
                <p className="mt-1 text-sm text-muted">
                  {activeJob.requirements.length
                    ? `${activeJob.requirements.length} extracted requirements are ready to analyze.`
                    : "No explicit requirements were extracted yet."}
                </p>
              </div>
              <Button
                loading={busyKey === `analyze-${activeJob.id}`}
                onClick={() => void runAnalysis(activeJob)}
              >
                <BriefcaseBusiness aria-hidden="true" className="size-4" />
                Analyze match
              </Button>
            </div>
            {activeJob.requirements.length > 0 && (
              <ul className="mt-4 grid gap-2 sm:grid-cols-2">
                {activeJob.requirements.slice(0, 8).map((requirement) => (
                  <li
                    className="rounded-lg border border-line bg-slate-50 p-3 text-sm"
                    key={requirement.id}
                  >
                    <span className="font-bold text-foreground">
                      {humanize(requirement.importance)}
                    </span>
                    <span className="mt-1 block text-muted">
                      {requirement.text}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="rounded-lg border border-line bg-white p-5 shadow-sm">
              <div className="grid gap-4 lg:grid-cols-[14rem_minmax(0,1fr)]">
                <div>
                  <p className="text-sm font-bold text-muted">Readiness</p>
                  <p className="mt-1 text-4xl font-black text-foreground">
                    {activeAnalysis.displayScore ?? "Needs evidence"}
                    {activeAnalysis.displayScore !== null && (
                      <span className="text-lg text-muted">/100</span>
                    )}
                  </p>
                  <Badge
                    tone={scoreTone(activeAnalysis.displayScore)}
                    className="mt-2"
                  >
                    {humanize(activeAnalysis.readinessLabel)}
                  </Badge>
                </div>
                <div className="space-y-3">
                  {activeAnalysis.displayScore !== null ? (
                    <ScoreBar
                      label="Application readiness"
                      score={activeAnalysis.displayScore}
                      tone={scoreTone(activeAnalysis.displayScore)}
                    />
                  ) : (
                    <Alert title="More evidence needed" tone="warning">
                      {activeAnalysis.insufficientReason ??
                        "Add confirmed career evidence before relying on this score."}
                    </Alert>
                  )}
                  <p className="text-sm leading-6 text-muted">
                    {activeAnalysis.summary}
                  </p>
                  <p className="text-xs leading-5 text-muted">
                    {activeAnalysis.scoringDisclaimer}
                  </p>
                  <Link
                    className={cn(
                      buttonStyles.base,
                      buttonStyles.secondary,
                      "w-fit",
                    )}
                    href={`/change-studio?analysisId=${activeAnalysis.id}`}
                  >
                    <FileDiff aria-hidden="true" className="size-4" />
                    Open Change Studio
                  </Link>
                </div>
              </div>
            </div>

            <div className="data-region table-scroll">
              <table className="w-full min-w-[720px] border-collapse text-left text-sm">
                <caption className="sr-only">
                  Requirement-by-requirement job match evidence matrix
                </caption>
                <thead className="bg-slate-50 text-xs uppercase text-muted">
                  <tr>
                    <th className="px-4 py-3" scope="col">
                      Requirement
                    </th>
                    <th className="px-4 py-3" scope="col">
                      Match
                    </th>
                    <th className="px-4 py-3" scope="col">
                      Evidence
                    </th>
                    <th className="px-4 py-3" scope="col">
                      Action
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {activeAnalysis.requirements.map((requirement) => (
                    <tr key={requirement.id}>
                      <td className="px-4 py-3 align-top">
                        <p className="font-bold text-foreground">
                          {requirement.requirementText}
                        </p>
                        <p className="mt-1 text-xs text-muted">
                          {humanize(requirement.importance)} /{" "}
                          {humanize(requirement.requirementType)}
                        </p>
                      </td>
                      <td className="px-4 py-3 align-top">
                        <Badge tone={stateTone(requirement.matchState)}>
                          {humanize(requirement.matchState)}
                        </Badge>
                        {requirement.hardGap && (
                          <p className="mt-2 text-xs font-bold text-warning-strong">
                            Mandatory gap
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3 align-top">
                        {requirement.evidence.length ? (
                          <ul className="space-y-2">
                            {requirement.evidence.map((link) => (
                              <li key={link.id}>
                                <span className="font-bold text-foreground">
                                  {link.evidenceTitle}
                                </span>
                                <span className="block text-xs text-muted">
                                  {humanize(link.evidenceStrength)}
                                </span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <span className="text-muted">
                            No eligible evidence
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 align-top text-muted">
                        {requirement.recommendedAction}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      <section
        aria-labelledby="priority-heading"
        className="rounded-lg border border-line bg-white p-5 shadow-sm"
      >
        <h2
          className="text-lg font-black text-foreground"
          id="priority-heading"
        >
          Opportunity priority
        </h2>
        {!activeAnalysis || !activeJob ? (
          <p className="mt-2 text-sm text-muted">
            Analyze a saved job before calculating opportunity priority.
          </p>
        ) : (
          <div className="mt-4 grid gap-5 xl:grid-cols-[minmax(0,1fr)_24rem]">
            <form
              className="grid gap-3 sm:grid-cols-2"
              onSubmit={(event) => void submitPriority(event)}
            >
              <label className="text-sm font-bold text-foreground">
                Interest
                <Input
                  defaultValue={4}
                  max={5}
                  min={1}
                  name="userInterest"
                  type="number"
                />
              </label>
              <label className="text-sm font-bold text-foreground">
                Career direction fit
                <Input
                  defaultValue={4}
                  max={5}
                  min={1}
                  name="careerDirectionFit"
                  type="number"
                />
              </label>
              <label className="text-sm font-bold text-foreground">
                Compensation fit
                <Select className="mt-1" name="compensationFit">
                  {preferenceFits.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="text-sm font-bold text-foreground">
                Location fit
                <Select className="mt-1" name="locationFit">
                  {preferenceFits.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="text-sm font-bold text-foreground">
                Work model fit
                <Select className="mt-1" name="workModelFit">
                  {preferenceFits.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="text-sm font-bold text-foreground">
                Tailoring effort
                <Select
                  className="mt-1"
                  defaultValue="medium"
                  name="tailoringEffort"
                >
                  {tailoringEfforts.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="text-sm font-bold text-foreground">
                Existing contacts
                <Input
                  defaultValue={0}
                  max={100}
                  min={0}
                  name="existingContacts"
                  type="number"
                />
              </label>
              <div className="self-end">
                <Button loading={busyKey === "priority"} type="submit">
                  <BriefcaseBusiness aria-hidden="true" className="size-4" />
                  Calculate priority
                </Button>
              </div>
            </form>

            {priority ? (
              <div aria-live="polite" className="rounded-lg bg-slate-50 p-4">
                <p className="text-sm font-bold text-muted">Priority</p>
                <div className="mt-2 flex items-center gap-3">
                  <Badge
                    tone={
                      priority.priorityLabel === "high" ? "success" : "primary"
                    }
                  >
                    {humanize(priority.priorityLabel)}
                  </Badge>
                  <span className="font-black text-foreground">
                    {Math.round(priority.priorityScoreBasisPoints / 100)}/100
                  </span>
                </div>
                <p className="mt-3 text-sm text-foreground">
                  {priority.nextAction}
                </p>
                <ul className="mt-3 space-y-2 text-sm text-muted">
                  {priority.reasonsFor.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
                {priority.blockers.length > 0 && (
                  <Alert className="mt-3" title="Reconsider" tone="warning">
                    {priority.blockers.join(" ")}
                  </Alert>
                )}
              </div>
            ) : (
              <div className="rounded-lg bg-slate-50 p-4 text-sm text-muted">
                Priority output appears here after calculation.
              </div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}

export function JobMatchLoading() {
  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
      <LoadingSkeleton />
    </main>
  );
}

export function JobMatchRouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
      <ErrorState
        description={error.message || "Refresh and try again."}
        onRetry={reset}
        title="Job Match unavailable"
      />
    </main>
  );
}
