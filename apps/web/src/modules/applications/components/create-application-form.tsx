"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from "react";

import {
  Alert,
  Button,
  EmptyState,
  Input,
  LoadingSkeleton,
  Select,
  buttonStyles,
} from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  createApplication,
  listApplicationSourceJobs,
  listApplicationSourceResumes,
  listApplicationSourceResumeVersions,
} from "../api/applications-api";
import type {
  ApplicationDetail,
  ApplicationStage,
  SavedJob,
  SavedResume,
  SavedResumeVersion,
} from "../api/types";
import { applicationStages, formatDate, humanize } from "./application-options";

type ResumeVersionLoadState =
  | { resumeId: string; status: "pending" }
  | {
      resumeId: string;
      status: "success";
      versions: SavedResumeVersion[];
    }
  | { message: string; resumeId: string; status: "error" };

type JobLoadState =
  | { query: string; status: "pending" }
  | {
      jobs: SavedJob[];
      nextCursor: string | null;
      query: string;
      status: "success";
    }
  | { message: string; query: string; status: "error" };

const JOB_PAGE_SIZE = 25;

export function CreateApplicationForm({
  onCreated,
}: {
  onCreated: (application: ApplicationDetail) => void;
}) {
  const [jobState, setJobState] = useState<JobLoadState>();
  const jobRequest = useRef(0);
  const [jobSearch, setJobSearch] = useState("");
  const [selectedJob, setSelectedJob] = useState<SavedJob>();
  const [loadingMoreJobs, setLoadingMoreJobs] = useState(false);
  const [jobPageFailure, setJobPageFailure] = useState<string>();
  const [resumes, setResumes] = useState<SavedResume[]>();
  const [versionState, setVersionState] = useState<ResumeVersionLoadState>();
  const versionRequest = useRef(0);
  const [resumeId, setResumeId] = useState("");
  const [sourceFailure, setSourceFailure] = useState<string>();
  const [failure, setFailure] = useState<string>();
  const [busy, setBusy] = useState(false);
  const idempotencyKey = useRef<string | undefined>(undefined);

  function currentIdempotencyKey(): string {
    idempotencyKey.current ??= crypto.randomUUID();
    return idempotencyKey.current;
  }

  function renewIntent() {
    idempotencyKey.current = crypto.randomUUID();
  }

  const loadResumeVersions = useCallback(async (nextResumeId: string) => {
    const requestId = ++versionRequest.current;
    if (!nextResumeId) {
      setVersionState({
        resumeId: nextResumeId,
        status: "success",
        versions: [],
      });
      return;
    }
    setVersionState({ resumeId: nextResumeId, status: "pending" });
    try {
      const versions = await listApplicationSourceResumeVersions(nextResumeId);
      if (requestId !== versionRequest.current) return;
      setVersionState({
        resumeId: nextResumeId,
        status: "success",
        versions,
      });
    } catch (error) {
      if (requestId !== versionRequest.current) return;
      setVersionState({
        message: requestErrorMessage(
          error,
          "Resume versions could not be loaded.",
        ),
        resumeId: nextResumeId,
        status: "error",
      });
    }
  }, []);

  const loadJobs = useCallback(async (nextQuery: string, cursor?: string) => {
    const query = nextQuery.trim();
    const requestId = ++jobRequest.current;
    const loadingMore = Boolean(cursor);
    setJobPageFailure(undefined);
    if (loadingMore) {
      setLoadingMoreJobs(true);
    } else {
      setJobSearch(query);
      setJobState({ query, status: "pending" });
      setLoadingMoreJobs(false);
    }
    try {
      const page = await listApplicationSourceJobs({
        ...(cursor ? { cursor } : {}),
        limit: JOB_PAGE_SIZE,
        ...(query ? { q: query } : {}),
      });
      if (requestId !== jobRequest.current) return;
      if (loadingMore && cursor) {
        setJobState((current) => {
          if (
            current?.status !== "success" ||
            current.query !== query ||
            current.nextCursor !== cursor
          ) {
            return current;
          }
          const known = new Set(current.jobs.map((job) => job.id));
          return {
            jobs: [
              ...current.jobs,
              ...page.data.filter((job) => !known.has(job.id)),
            ],
            nextCursor: page.page.nextCursor,
            query,
            status: "success",
          };
        });
      } else {
        setJobState({
          jobs: page.data,
          nextCursor: page.page.nextCursor,
          query,
          status: "success",
        });
        setSelectedJob((current) => current ?? page.data[0]);
      }
    } catch (error) {
      if (requestId !== jobRequest.current) return;
      const message = requestErrorMessage(
        error,
        loadingMore
          ? "More saved jobs could not be loaded."
          : "Saved jobs could not be loaded.",
      );
      if (loadingMore) {
        setJobPageFailure(message);
      } else {
        setJobState({ message, query, status: "error" });
      }
    } finally {
      if (requestId === jobRequest.current) setLoadingMoreJobs(false);
    }
  }, []);

  const loadResumes = useCallback(async () => {
    setSourceFailure(undefined);
    setResumes(undefined);
    try {
      const resumeItems = await listApplicationSourceResumes();
      setResumes(resumeItems);
      const nextResumeId = resumeItems[0]?.id || "";
      setResumeId(nextResumeId);
      void loadResumeVersions(nextResumeId);
    } catch (error) {
      setSourceFailure(
        requestErrorMessage(error, "Saved resumes could not be loaded."),
      );
    }
  }, [loadResumeVersions]);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      void loadJobs("");
      void loadResumes();
    });
    return () => {
      active = false;
      jobRequest.current += 1;
      versionRequest.current += 1;
    };
  }, [loadJobs, loadResumes]);

  const selectedResume = useMemo(
    () => resumes?.find((resume) => resume.id === resumeId),
    [resumeId, resumes],
  );
  const visibleVersionState =
    versionState?.resumeId === resumeId ? versionState : undefined;
  const versions =
    visibleVersionState?.status === "success"
      ? visibleVersionState.versions
      : undefined;
  const jobOptions = useMemo(() => {
    const jobs = jobState?.status === "success" ? jobState.jobs : [];
    return selectedJob && !jobs.some((job) => job.id === selectedJob.id)
      ? [selectedJob, ...jobs]
      : jobs;
  }, [jobState, selectedJob]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true);
    setFailure(undefined);
    try {
      const application = await createApplication(
        {
          applicationDeadline:
            String(form.get("applicationDeadline") ?? "") || null,
          contacts: [],
          followUpAt: String(form.get("followUpAt") ?? "") || null,
          jobId: String(form.get("jobId")),
          referralStatus: "none",
          resumeVersionId: String(form.get("resumeVersionId")),
          industry: String(form.get("industry") ?? "").trim() || null,
          source: String(form.get("source") ?? "").trim() || null,
          stage: String(form.get("stage")) as ApplicationStage,
        },
        currentIdempotencyKey(),
      );
      renewIntent();
      onCreated(application);
      formElement.reset();
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "The application could not be created."),
      );
    } finally {
      setBusy(false);
    }
  }

  if (!resumes) {
    return sourceFailure ? (
      <Alert title="Saved resumes unavailable" tone="danger">
        <p>{sourceFailure}</p>
        <Button
          className="mt-3 min-h-9 px-3"
          onClick={() => void loadResumes()}
        >
          Retry
        </Button>
      </Alert>
    ) : (
      <LoadingSkeleton />
    );
  }

  if ((!jobState || jobState.status === "pending") && !selectedJob) {
    return <LoadingSkeleton />;
  }

  if (jobState?.status === "error" && !selectedJob) {
    return (
      <Alert title="Saved jobs unavailable" tone="danger">
        <p>{jobState.message}</p>
        <Button
          className="mt-3 min-h-9 px-3"
          onClick={() => void loadJobs(jobState.query)}
        >
          Retry
        </Button>
      </Alert>
    );
  }

  if (!selectedJob || !resumes.length) {
    return (
      <EmptyState
        action={
          <div className="flex flex-wrap justify-center gap-2">
            {!selectedJob && (
              <Link
                className={`${buttonStyles.base} ${buttonStyles.primary}`}
                href="/job-match"
              >
                Save a job
              </Link>
            )}
            {!resumes.length && (
              <Link
                className={`${buttonStyles.base} ${buttonStyles.secondary}`}
                href="/resume-builder"
              >
                Build a resume
              </Link>
            )}
          </div>
        }
        description="An application must pin both a saved job and an immutable resume version."
        title="Complete the application sources"
      />
    );
  }

  return (
    <form
      className="grid gap-4 md:grid-cols-2"
      onChange={renewIntent}
      onSubmit={(event) => void submit(event)}
    >
      {failure && (
        <Alert
          className="md:col-span-2"
          title="Could not continue"
          tone="danger"
        >
          {failure}
        </Alert>
      )}
      <div
        className="grid gap-2 md:col-span-2 sm:grid-cols-[minmax(0,1fr)_auto_auto]"
        role="search"
      >
        <label className="text-sm font-bold text-foreground">
          Search saved jobs
          <Input
            className="mt-1"
            maxLength={160}
            onChange={(event) => setJobSearch(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== "Enter") return;
              event.preventDefault();
              void loadJobs(jobSearch);
            }}
            placeholder="Job title or company"
            type="search"
            value={jobSearch}
          />
        </label>
        <Button
          className="self-end"
          onClick={() => void loadJobs(jobSearch)}
          type="button"
          variant="secondary"
        >
          Search jobs
        </Button>
        {jobState?.query && (
          <Button
            className="self-end"
            onClick={() => {
              setJobSearch("");
              void loadJobs("");
            }}
            type="button"
            variant="ghost"
          >
            Show all
          </Button>
        )}
      </div>

      {jobState?.status === "pending" && (
        <p className="text-sm text-muted md:col-span-2" role="status">
          Searching saved jobs...
        </p>
      )}
      {jobState?.status === "error" && (
        <Alert
          className="md:col-span-2"
          title="Saved job search unavailable"
          tone="danger"
        >
          <p>{jobState.message}</p>
          <Button
            className="mt-3 min-h-9 px-3"
            onClick={() => void loadJobs(jobState.query)}
            type="button"
            variant="secondary"
          >
            Retry job search
          </Button>
        </Alert>
      )}
      {jobPageFailure && jobState?.status === "success" && (
        <Alert
          className="md:col-span-2"
          title="More saved jobs unavailable"
          tone="danger"
        >
          <p>{jobPageFailure}</p>
          {jobState.nextCursor && (
            <Button
              className="mt-3 min-h-9 px-3"
              onClick={() =>
                void loadJobs(jobState.query, jobState.nextCursor ?? undefined)
              }
              type="button"
              variant="secondary"
            >
              Retry more jobs
            </Button>
          )}
        </Alert>
      )}
      {jobState?.status === "success" && jobState.jobs.length === 0 && (
        <p className="text-sm text-muted md:col-span-2" role="status">
          No saved jobs match this search. Your current selection is preserved.
        </p>
      )}
      <label className="text-sm font-bold text-foreground">
        Saved job
        <Select
          aria-busy={jobState?.status === "pending" || undefined}
          className="mt-1"
          disabled={jobState?.status === "pending" || !jobOptions.length}
          name="jobId"
          onChange={(event) =>
            setSelectedJob(
              jobOptions.find((job) => job.id === event.target.value),
            )
          }
          required
          value={selectedJob.id}
        >
          {jobOptions.map((job) => (
            <option key={job.id} value={job.id}>
              {job.title}
              {job.company ? ` — ${job.company}` : ""}
            </option>
          ))}
        </Select>
      </label>
      {jobState?.status === "success" && jobState.nextCursor && (
        <div className="flex items-end">
          <Button
            loading={loadingMoreJobs}
            onClick={() =>
              void loadJobs(jobState.query, jobState.nextCursor ?? undefined)
            }
            type="button"
            variant="secondary"
          >
            Load more saved jobs
          </Button>
        </div>
      )}
      <label className="text-sm font-bold text-foreground">
        Resume
        <Select
          className="mt-1"
          onChange={(event) => {
            const nextResumeId = event.target.value;
            setResumeId(nextResumeId);
            void loadResumeVersions(nextResumeId);
          }}
          value={resumeId}
        >
          {resumes.map((resume) => (
            <option key={resume.id} value={resume.id}>
              {resume.title}
            </option>
          ))}
        </Select>
      </label>
      <div>
        <label className="text-sm font-bold text-foreground">
          Immutable resume version
          <Select
            aria-busy={visibleVersionState?.status === "pending" || undefined}
            className="mt-1"
            disabled={!versions?.length}
            name="resumeVersionId"
            required
          >
            {visibleVersionState?.status === "pending" && (
              <option>Loading resume versions...</option>
            )}
            {visibleVersionState?.status === "error" && (
              <option>Resume versions unavailable</option>
            )}
            {versions?.length === 0 && (
              <option>No immutable versions available</option>
            )}
            {versions?.map((version) => (
              <option key={version.id} value={version.id}>
                Version {version.versionNumber} —{" "}
                {formatDate(version.createdAt)}
                {selectedResume?.currentVersionId === version.id
                  ? " (current)"
                  : ""}
              </option>
            ))}
          </Select>
          <span className="mt-1 block text-xs font-normal text-muted">
            The selected version is pinned for an auditable application history.
          </span>
        </label>
        {visibleVersionState?.status === "error" && (
          <Alert
            className="mt-3"
            title="Resume versions unavailable"
            tone="danger"
          >
            <p>{visibleVersionState.message}</p>
            <Button
              className="mt-3 min-h-9 px-3"
              onClick={() => void loadResumeVersions(resumeId)}
              variant="secondary"
            >
              Retry resume versions
            </Button>
          </Alert>
        )}
        {versions?.length === 0 && (
          <Alert
            className="mt-3"
            title="No immutable resume versions"
            tone="warning"
          >
            <p>Create a resume version before adding this application.</p>
            <Link
              className={`${buttonStyles.base} ${buttonStyles.secondary} mt-3`}
              href="/resume-builder"
            >
              Open resume builder
            </Link>
          </Alert>
        )}
      </div>
      <label className="text-sm font-bold text-foreground">
        Initial stage
        <Select className="mt-1" defaultValue="saved" name="stage">
          {applicationStages.map((stage) => (
            <option key={stage} value={stage}>
              {humanize(stage)}
            </option>
          ))}
        </Select>
      </label>
      <label className="text-sm font-bold text-foreground">
        Application deadline
        <Input className="mt-1" name="applicationDeadline" type="date" />
      </label>
      <label className="text-sm font-bold text-foreground">
        Follow-up date
        <Input className="mt-1" name="followUpAt" type="date" />
      </label>
      <label className="text-sm font-bold text-foreground">
        Application source
        <Input
          className="mt-1"
          maxLength={120}
          name="source"
          placeholder="For example, referral or company site"
        />
      </label>
      <label className="text-sm font-bold text-foreground">
        Industry
        <Input className="mt-1" maxLength={120} name="industry" />
      </label>
      <div className="md:col-span-2">
        <Button
          disabled={!versions?.length || jobState?.status === "pending"}
          loading={busy}
          type="submit"
        >
          Add application
        </Button>
      </div>
    </form>
  );
}
