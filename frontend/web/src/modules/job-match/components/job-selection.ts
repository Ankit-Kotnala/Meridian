import type { Job, JobCatalogListing, JobMatchAnalysis } from "../api/types";

/**
 * One selected opportunity, whichever list it came from.
 *
 * The detail panel shows catalog listings and saved jobs side by side, and a
 * listing becomes a saved job mid-session without the selection changing. Both
 * are normalized to this shape so the panel never has to branch on which of the
 * two it is holding — `job` is simply present once the opportunity is saved.
 */
export type JobSelection = {
  applicationUrl: string | null;
  company: string | null;
  job: Job | undefined;
  key: string;
  location: string | null;
  platform: string | null;
  remote: boolean;
  sourceText: string | null;
  title: string;
};

export function listingKey(
  listing: Pick<JobCatalogListing, "externalId" | "platform">,
): string {
  return `${listing.platform}:${listing.externalId}`;
}

export function jobKey(job: Job): string {
  return `job:${job.id}`;
}

export function selectionFromListing(
  listing: JobCatalogListing,
  job: Job | undefined,
): JobSelection {
  return {
    applicationUrl: listing.applicationUrl ?? job?.sourceUrl ?? null,
    company: listing.company ?? null,
    job,
    key: listingKey(listing),
    location: listing.location ?? null,
    platform: listing.platform,
    remote: listing.remote === true,
    sourceText: listing.sourceText,
    title: listing.title,
  };
}

export function selectionFromJob(job: Job): JobSelection {
  return {
    applicationUrl: job.sourceUrl ?? null,
    company: job.company ?? null,
    job,
    key: jobKey(job),
    location: job.location ?? null,
    platform: null,
    remote: job.workModel === "remote",
    sourceText: null,
    title: job.title,
  };
}

/** Share of extracted requirements backed by at least transferable evidence. */
export function requirementCoverage(analysis: JobMatchAnalysis): {
  covered: number;
  percent: number;
  total: number;
} {
  const total = analysis.requirements.length;
  const covered = analysis.requirements.filter((requirement) =>
    ["strong", "partial", "transferable"].includes(requirement.matchState),
  ).length;
  return {
    covered,
    percent: total === 0 ? 0 : Math.round((covered / total) * 100),
    total,
  };
}
