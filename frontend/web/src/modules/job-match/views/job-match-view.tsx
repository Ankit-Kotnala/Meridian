"use client";

import {
  BriefcaseBusiness,
  FileDiff,
  RefreshCcw,
  Search,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Input,
  LoadingSkeleton,
  ScoreBar,
  Select,
  buttonStyles,
  cn,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import { JobDetailPanel } from "../components/job-detail-panel";
import { JobFiltersPanel } from "../components/job-filters-panel";
import { JobListingResults } from "../components/job-listing-results";
import {
  emptyJobSearchFilters,
  filterOptionsFrom,
  hasActiveFilters,
  listingMatchesFilters,
  type JobSearchFilters,
} from "../components/job-search-filters";
import {
  listingKey,
  selectionFromListing,
  type JobSelection,
} from "../components/job-selection";
import { RoleFilterPicker } from "../components/role-filter-picker";
import {
  analyzeJob,
  browseJobCatalog,
  createApplicationForJob,
  deleteJob,
  generateAssistedApplyPack,
  getJobCatalogSuggestions,
  getJobs,
  listResumesForApply,
  prioritizeOpportunity,
  saveJobCatalogListing,
  setJobCatalogRolePreferences,
} from "../api/job-match-api";
import type {
  Job,
  JobCatalogListing,
  JobCatalogSearch,
  JobMatchAnalysis,
  JobSourceKind,
  OpportunityPriority,
  PreferenceFit,
  TailoringEffort,
} from "../api/types";

const sourceKinds: Array<{ label: string; value: JobSourceKind | "" }> = [
  { label: "Any source", value: "" },
  { label: "Pasted", value: "paste" },
  { label: "URL import", value: "url" },
  { label: "Manual", value: "manual" },
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

const CATALOG_SEARCH_LIMIT = 50;

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

/** A catalog listing and a saved job describe the same opening on both sides. */
function sameOpening(listing: JobCatalogListing, job: Job): boolean {
  const normalize = (value: string | null | undefined) =>
    (value ?? "").trim().toLowerCase();
  return (
    normalize(listing.title) === normalize(job.title) &&
    normalize(listing.company) === normalize(job.company)
  );
}

export type JobMatchSection = "search" | "saved" | "roles";

export function JobMatchView({
  roleMatchingPanel,
  section = "search",
}: {
  roleMatchingPanel?: ReactNode;
  section?: JobMatchSection;
}) {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>();
  const [suggestions, setSuggestions] = useState<JobCatalogSearch>();
  const [rolePreferenceBusy, setRolePreferenceBusy] = useState(false);
  const [savingListingKey, setSavingListingKey] = useState<string>();
  const [activeJobId, setActiveJobId] = useState<string>();
  const [activeAnalysis, setActiveAnalysis] = useState<JobMatchAnalysis>();
  const [priority, setPriority] = useState<OpportunityPriority>();
  const [query, setQuery] = useState("");
  const [sourceKind, setSourceKind] = useState<JobSourceKind | "">("");
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [busyKey, setBusyKey] = useState<string>();
  const [filters, setFilters] = useState<JobSearchFilters>(
    emptyJobSearchFilters,
  );
  const [appliedFilters, setAppliedFilters] = useState<JobSearchFilters>(
    emptyJobSearchFilters,
  );
  const [catalogResults, setCatalogResults] = useState<JobCatalogListing[]>();
  const [filterBusy, setFilterBusy] = useState(false);
  const [selectedListing, setSelectedListing] = useState<JobCatalogListing>();

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

  const loadSuggestions = useCallback(async () => {
    try {
      setSuggestions(await getJobCatalogSuggestions());
    } catch {
      // Suggestions are a supplementary discovery aid; a failure here must
      // not block the core saved-jobs workflow above.
      setSuggestions(undefined);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
    queueMicrotask(() => void loadSuggestions());
  }, [load, loadSuggestions]);

  const serverSearched = catalogResults !== undefined;
  const sourceListings = useMemo(
    () => catalogResults ?? suggestions?.listings ?? [],
    [catalogResults, suggestions?.listings],
  );
  // The catalog keyword is answered by the server, so re-testing it in the
  // browser would drop listings matched on their body text rather than title.
  const clientFilters = useMemo(
    () =>
      serverSearched ? { ...appliedFilters, keyword: "" } : appliedFilters,
    [appliedFilters, serverSearched],
  );
  const visibleListings = useMemo(
    () =>
      sourceListings.filter((listing) =>
        listingMatchesFilters(listing, clientFilters),
      ),
    [clientFilters, sourceListings],
  );
  const filterOptions = useMemo(
    () => filterOptionsFrom(sourceListings),
    [sourceListings],
  );

  const savedJobFor = useCallback(
    (listing: JobCatalogListing) =>
      jobs?.find((job) => sameOpening(listing, job)),
    [jobs],
  );

  const savedKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const listing of sourceListings) {
      if (savedJobFor(listing)) keys.add(listingKey(listing));
    }
    return keys;
  }, [savedJobFor, sourceListings]);

  const refreshAll = useCallback(async () => {
    await Promise.all([load(), loadSuggestions()]);
  }, [load, loadSuggestions]);

  const selection: JobSelection | undefined = useMemo(
    () =>
      selectedListing
        ? selectionFromListing(selectedListing, savedJobFor(selectedListing))
        : undefined,
    [savedJobFor, selectedListing],
  );

  const panelAnalysis =
    selection?.job && activeAnalysis?.job?.id === selection.job.id
      ? activeAnalysis
      : undefined;
  const panelPriority = panelAnalysis ? priority : undefined;

  async function applyFilters() {
    setAppliedFilters(filters);
    const keyword = filters.keyword.trim();
    if (!keyword) {
      setCatalogResults(undefined);
      return;
    }
    setFilterBusy(true);
    setFailure(undefined);
    try {
      const page = await browseJobCatalog({
        limit: CATALOG_SEARCH_LIMIT,
        offset: 0,
        q: keyword,
      });
      setCatalogResults(page.listings);
    } catch (error) {
      setFailure(requestErrorMessage(error, "Job search failed."));
    } finally {
      setFilterBusy(false);
    }
  }

  function clearFilters() {
    setFilters(emptyJobSearchFilters);
    setAppliedFilters(emptyJobSearchFilters);
    setCatalogResults(undefined);
  }

  function openListing(listing: JobCatalogListing) {
    setSelectedListing(listing);
    const saved = savedJobFor(listing);
    setActiveJobId(saved?.id);
    setActiveAnalysis(undefined);
    setPriority(undefined);
  }

  async function ensureSavedJob(listing: JobCatalogListing): Promise<Job> {
    const existing = savedJobFor(listing);
    if (existing) return existing;
    const key = listingKey(listing);
    setSavingListingKey(key);
    try {
      const job = await saveJobCatalogListing(
        listing.platform,
        listing.externalId,
      );
      trackSavedJob(job, `${job.title} saved for matching.`);
      return job;
    } finally {
      setSavingListingKey(undefined);
    }
  }

  async function saveListing(listing: JobCatalogListing) {
    setFailure(undefined);
    setSuccess(undefined);
    try {
      await ensureSavedJob(listing);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "This listing could not be saved."),
      );
    }
  }

  async function analyzeListing(listing: JobCatalogListing) {
    setBusyKey(`analyze-${listingKey(listing)}`);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const job = await ensureSavedJob(listing);
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

  async function applyToListing(listing: JobCatalogListing) {
    setBusyKey(`apply-${listingKey(listing)}`);
    try {
      const job = await ensureSavedJob(listing);
      await applyForMe(job);
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "The application pack could not be prepared.",
        ),
      );
    } finally {
      setBusyKey(undefined);
    }
  }

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

  function trackSavedJob(job: Job, successMessage: string) {
    setJobs((current = []) => [
      job,
      ...current.filter((item) => item.id !== job.id),
    ]);
    setActiveJobId(job.id);
    setSuccess(successMessage);
  }

  async function updateRolePreference(nextRoleTitles: string[]) {
    setRolePreferenceBusy(true);
    setFailure(undefined);
    try {
      await setJobCatalogRolePreferences(nextRoleTitles);
      await loadSuggestions();
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "The role filter could not be updated."),
      );
    } finally {
      setRolePreferenceBusy(false);
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

  async function applyForMe(job: Job) {
    setBusyKey(`apply-${job.id}`);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const resumes = await listResumesForApply();
      if (resumes.length === 0) {
        setFailure(
          "Build a resume in Resumes first — applying needs a tailored resume version.",
        );
        return;
      }
      const resume = [...resumes].sort((a, b) =>
        b.updatedAt.localeCompare(a.updatedAt),
      )[0]!;
      const application = await createApplicationForJob(
        job.id,
        resume.currentVersionId,
      );
      await generateAssistedApplyPack(application.id);
      setSuccess(
        `${job.title}: application pack ready using "${resume.title}". Open Applications to review and submit it yourself — Meridian never submits for you.`,
      );
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "The application pack could not be prepared.",
        ),
      );
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
      <div className="py-6">
        <ErrorState
          description={failure}
          onRetry={() => void load()}
          title="Job Match unavailable"
        />
      </div>
    );
  }

  if (!jobs) {
    return (
      <div className="py-6">
        <LoadingSkeleton />
      </div>
    );
  }

  const resultsDescription = serverSearched
    ? `Matching “${appliedFilters.keyword.trim()}” across every published job board.`
    : !suggestions || suggestions.targetRoleTitles.length === 0
      ? "Recent listings from published job boards. Set a target role in Role matching for closer matches."
      : suggestions.matchedTargetRole
        ? `Matched toward ${suggestions.targetRoleTitles.join(", ")} from published job boards.`
        : `No current listings matched ${suggestions.targetRoleTitles.join(", ")} closely, so here are recent listings instead.`;

  const searchPanel = (
    <div className="space-y-4">
      <RoleFilterPicker
        action={
          <Button onClick={() => void refreshAll()} variant="secondary">
            <RefreshCcw aria-hidden="true" className="size-4" />
            Refresh
          </Button>
        }
        busy={rolePreferenceBusy}
        onChange={(next) => void updateRolePreference(next)}
        selected={suggestions?.selectedRoleTitles ?? []}
        suggested={suggestions?.suggestedRoleTitles ?? []}
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(16.5rem,18rem)_minmax(0,1fr)] xl:grid-cols-[minmax(16.5rem,18rem)_minmax(0,1fr)_25rem]">
        <JobFiltersPanel
          busy={filterBusy}
          filters={filters}
          locations={filterOptions.locations}
          onApply={() => void applyFilters()}
          onChange={setFilters}
          onClear={clearFilters}
          platforms={filterOptions.platforms}
        />

        <JobListingResults
          description={resultsDescription}
          listings={visibleListings}
          onOpen={openListing}
          onSave={(listing) => void saveListing(listing)}
          savedKeys={savedKeys}
          savingKey={savingListingKey}
          selectedKey={selection?.key}
          totalCount={
            hasActiveFilters(clientFilters)
              ? visibleListings.length
              : sourceListings.length
          }
        />

        {selection && selectedListing ? (
          <JobDetailPanel
            analysis={panelAnalysis}
            analyzing={busyKey === `analyze-${selection.key}`}
            applying={busyKey === `apply-${selection.key}`}
            onAnalyze={() => void analyzeListing(selectedListing)}
            onApply={() => void applyToListing(selectedListing)}
            onClose={() => setSelectedListing(undefined)}
            onOpenMatrix={() => {
              if (selection.job) setActiveJobId(selection.job.id);
              router.push("/job-match/saved");
            }}
            onSave={() => void saveListing(selectedListing)}
            priority={panelPriority}
            saving={savingListingKey === selection.key}
            selection={selection}
          />
        ) : (
          <Card as="aside" className="hidden xl:block">
            <div className="p-5">
              <EmptyState
                description="Select a job from the list to see its readiness, requirement matrix, and priority."
                title="No job selected"
              />
            </div>
          </Card>
        )}
      </div>
    </div>
  );

  const savedPanel = (
    <div className="space-y-6">
      <section aria-labelledby="saved-jobs-heading" className="space-y-4">
        <form
          className="surface-card rounded-[var(--radius-card)] p-4"
          onSubmit={(event) => void searchJobs(event)}
        >
          <h2
            className="text-base font-semibold tracking-[-0.01em] text-foreground"
            id="saved-jobs-heading"
          >
            Saved jobs
          </h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem_auto] sm:items-end">
            <label className="text-xs font-semibold text-muted-strong">
              Search
              <Input
                className="mt-1.5"
                maxLength={160}
                onChange={(event) => setQuery(event.target.value)}
                type="search"
                value={query}
              />
            </label>
            <label className="text-xs font-semibold text-muted-strong">
              Source
              <Select
                className="mt-1.5"
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
              Search saved jobs
            </Button>
          </div>
        </form>

        {jobs.length === 0 ? (
          <EmptyState
            description="Saved job postings will appear here."
            title="No saved jobs"
          />
        ) : (
          <ul className="grid gap-3 md:grid-cols-2">
            {jobs.map((job) => {
              const active = activeJob?.id === job.id;
              return (
                <li
                  className={cn(
                    "surface-card rounded-[var(--radius-card)] p-4",
                    active && "ring-1 ring-primary",
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
                    <span className="block text-sm font-semibold text-foreground">
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
                  <div className="mt-3 flex flex-wrap gap-2">
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
                      loading={busyKey === `apply-${job.id}`}
                      onClick={() => void applyForMe(job)}
                    >
                      Apply for me
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
      </section>

      <section aria-labelledby="analysis-heading" className="space-y-4">
        <h2
          className="text-base font-semibold tracking-[-0.01em] text-foreground"
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
          <div className="surface-card rounded-[var(--radius-card)] p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h3 className="text-sm font-semibold text-foreground">
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
                    className="rounded-[var(--radius-control)] border border-line bg-surface-subtle p-3 text-sm"
                    key={requirement.id}
                  >
                    <span className="font-semibold text-foreground">
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
            <div className="surface-card rounded-[var(--radius-card)] p-5">
              <div className="grid gap-4 lg:grid-cols-[14rem_minmax(0,1fr)]">
                <div>
                  <p className="text-sm font-semibold text-muted">Readiness</p>
                  <p className="mt-1 text-4xl font-semibold text-foreground">
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
                <thead className="bg-surface-subtle text-xs uppercase text-muted">
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
                        <p className="font-semibold text-foreground">
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
                          <p className="mt-2 text-xs font-semibold text-warning-strong">
                            Mandatory gap
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3 align-top">
                        {requirement.evidence.length ? (
                          <ul className="space-y-2">
                            {requirement.evidence.map((link) => (
                              <li key={link.id}>
                                <span className="font-semibold text-foreground">
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
        className="surface-card rounded-[var(--radius-card)] p-5"
      >
        <h2
          className="text-base font-semibold tracking-[-0.01em] text-foreground"
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
              <label className="text-sm font-semibold text-foreground">
                Interest
                <Input
                  defaultValue={4}
                  max={5}
                  min={1}
                  name="userInterest"
                  type="number"
                />
              </label>
              <label className="text-sm font-semibold text-foreground">
                Career direction fit
                <Input
                  defaultValue={4}
                  max={5}
                  min={1}
                  name="careerDirectionFit"
                  type="number"
                />
              </label>
              <label className="text-sm font-semibold text-foreground">
                Compensation fit
                <Select className="mt-1" name="compensationFit">
                  {preferenceFits.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="text-sm font-semibold text-foreground">
                Location fit
                <Select className="mt-1" name="locationFit">
                  {preferenceFits.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="text-sm font-semibold text-foreground">
                Work model fit
                <Select className="mt-1" name="workModelFit">
                  {preferenceFits.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="text-sm font-semibold text-foreground">
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
              <label className="text-sm font-semibold text-foreground">
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
              <div
                aria-live="polite"
                className="rounded-[var(--radius-card)] bg-surface-subtle p-4"
              >
                <p className="text-sm font-semibold text-muted">Priority</p>
                <div className="mt-2 flex items-center gap-3">
                  <Badge
                    tone={
                      priority.priorityLabel === "high" ? "success" : "primary"
                    }
                  >
                    {humanize(priority.priorityLabel)}
                  </Badge>
                  <span className="font-semibold text-foreground">
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
              <div className="rounded-[var(--radius-card)] bg-surface-subtle p-4 text-sm text-muted">
                Priority output appears here after calculation.
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );

  // Alerts live inside the gutter with the panel rather than above the bar, so
  // they read as part of the tab the owner is looking at.
  const panelShell = (content: ReactNode) => (
    <div className="workspace-page space-y-4">
      {failure && (
        <Alert title="Request failed" tone="danger">
          {failure}
        </Alert>
      )}
      {success && (
        <Alert title="Saved" tone="success">
          {success}
        </Alert>
      )}
      {content}
    </div>
  );

  const panel =
    section === "saved"
      ? panelShell(savedPanel)
      : section === "roles"
        ? panelShell(
            roleMatchingPanel ?? (
              <EmptyState
                description="Role readiness is unavailable on this page."
                title="Role matching"
              />
            ),
          )
        : panelShell(searchPanel);

  return (
    <>
      <div aria-live="polite" className="sr-only">
        {success || failure || ""}
      </div>
      {panel}
    </>
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
