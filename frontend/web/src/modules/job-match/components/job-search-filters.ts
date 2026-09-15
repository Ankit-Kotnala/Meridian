import type { JobCatalogListing } from "../api/types";

/**
 * Client-side narrowing for the job search results list.
 *
 * Keyword and location are sent to the catalog browse API; seniority and work
 * model are derived from listing text for the rows already loaded.
 */

export type SeniorityFilter =
  "" | "internship" | "junior" | "mid" | "senior" | "staff" | "principal";

export type WorkModelFilter = "" | "remote" | "hybrid" | "onsite";

export type JobSearchFilters = {
  keyword: string;
  location: string;
  platform: string;
  seniority: SeniorityFilter;
  workModel: WorkModelFilter;
};

export const emptyJobSearchFilters: JobSearchFilters = {
  keyword: "",
  location: "",
  platform: "",
  seniority: "",
  workModel: "",
};

export const seniorityOptions: Array<{
  label: string;
  value: SeniorityFilter;
}> = [
  { label: "Any seniority", value: "" },
  { label: "Internship", value: "internship" },
  { label: "Junior", value: "junior" },
  { label: "Mid-level", value: "mid" },
  { label: "Senior", value: "senior" },
  { label: "Staff", value: "staff" },
  { label: "Principal", value: "principal" },
];

export const workModelOptions: Array<{
  label: string;
  value: WorkModelFilter;
}> = [
  { label: "Remote / Hybrid / On-site", value: "" },
  { label: "Remote", value: "remote" },
  { label: "Hybrid", value: "hybrid" },
  { label: "On-site", value: "onsite" },
];

// Ordered most-specific first: "Senior Staff Engineer" is staff, and an
// internship advertised as "Senior year internship" is still an internship.
const seniorityPatterns: Array<[Exclude<SeniorityFilter, "">, RegExp]> = [
  ["internship", /\b(intern|internship|trainee|apprentice)\b/],
  ["principal", /\b(principal|distinguished|fellow|director|head of|vp)\b/],
  ["staff", /\b(staff|architect)\b/],
  ["senior", /\b(senior|sr\.?|lead)\b/],
  ["junior", /\b(junior|jr\.?|graduate|entry[- ]level|associate)\b/],
];

export function listingSeniority(title: string): Exclude<SeniorityFilter, ""> {
  const normalized = title.toLowerCase();
  for (const [value, pattern] of seniorityPatterns) {
    if (pattern.test(normalized)) return value;
  }
  return "mid";
}

export function listingWorkModel(
  listing: Pick<JobCatalogListing, "location" | "remote" | "title">,
): Exclude<WorkModelFilter, ""> {
  const text = `${listing.title} ${listing.location ?? ""}`.toLowerCase();
  // Checked before the remote flag: a board that flags a hybrid role as remote
  // is describing the same job the words already describe more precisely.
  if (/\bhybrid\b/.test(text)) return "hybrid";
  if (listing.remote === true || /\b(remote|anywhere|worldwide)\b/.test(text)) {
    return "remote";
  }
  return "onsite";
}

export function listingMatchesFilters(
  listing: JobCatalogListing,
  filters: JobSearchFilters,
): boolean {
  if (filters.platform && listing.platform !== filters.platform) return false;
  if (
    filters.seniority &&
    listingSeniority(listing.title) !== filters.seniority
  ) {
    return false;
  }
  if (filters.workModel && listingWorkModel(listing) !== filters.workModel) {
    return false;
  }
  if (filters.location) {
    const needle = filters.location.trim().toLowerCase();
    if (!(listing.location ?? "").toLowerCase().includes(needle)) return false;
  }
  const keyword = filters.keyword.trim().toLowerCase();
  if (!keyword) return true;
  return [listing.title, listing.company, listing.location]
    .filter(Boolean)
    .some((value) => value!.toLowerCase().includes(keyword));
}

/** Distinct values present in the current results, so no filter is a dead end. */
export function filterOptionsFrom(listings: readonly JobCatalogListing[]): {
  locations: string[];
  platforms: string[];
} {
  const locations = new Set<string>();
  const platforms = new Set<string>();
  for (const listing of listings) {
    if (listing.location?.trim()) locations.add(listing.location.trim());
    if (listing.platform) platforms.add(listing.platform);
  }
  return {
    locations: [...locations].sort((a, b) => a.localeCompare(b)),
    platforms: [...platforms].sort((a, b) => a.localeCompare(b)),
  };
}

export function humanizePlatform(platform: string): string {
  if (platform === "linkedin") return "LinkedIn";
  return platform
    .split(/[-_]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function hasActiveFilters(filters: JobSearchFilters): boolean {
  return (
    filters.keyword.trim() !== "" ||
    filters.location !== "" ||
    filters.platform !== "" ||
    filters.seniority !== "" ||
    filters.workModel !== ""
  );
}
