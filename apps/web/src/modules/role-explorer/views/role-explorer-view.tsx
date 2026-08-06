"use client";

import {
  Bookmark,
  Check,
  GitCompare,
  RefreshCcw,
  Save,
  Search,
  Target,
  Trash2,
} from "lucide-react";
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
  LoadingSkeleton,
  PageHeader,
  ScoreBar,
  Select,
  cn,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  analyzeRole,
  compareRoles,
  deleteSavedRole,
  getReadinessHistory,
  getRoles,
  getSavedRoles,
  saveRole,
  updateSavedRole,
} from "../api/role-explorer-api";
import type {
  Role,
  RoleComparison,
  RoleReadiness,
  RoleSeniority,
  SavedRole,
} from "../api/types";

const seniorities: Array<{ label: string; value: RoleSeniority | "" }> = [
  { label: "Any seniority", value: "" },
  { label: "Entry", value: "entry" },
  { label: "Mid", value: "mid" },
  { label: "Senior", value: "senior" },
  { label: "Lead", value: "lead" },
  { label: "Executive", value: "executive" },
];

function label(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function scoreTone(score: number | null | undefined) {
  if (score === null || score === undefined) return "warning" as const;
  if (score >= 75) return "success" as const;
  if (score >= 55) return "primary" as const;
  return "warning" as const;
}

function savedForRole(savedRoles: SavedRole[], roleId: string) {
  return savedRoles.find((item) => item.role.id === roleId);
}

export function RoleExplorerView() {
  const [roles, setRoles] = useState<Role[]>();
  const [savedRoles, setSavedRoles] = useState<SavedRole[]>();
  const [history, setHistory] = useState<RoleReadiness[]>([]);
  const [activeAnalysis, setActiveAnalysis] = useState<RoleReadiness>();
  const [comparison, setComparison] = useState<RoleComparison>();
  const [query, setQuery] = useState("");
  const [seniority, setSeniority] = useState<RoleSeniority | "">("");
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [busyKey, setBusyKey] = useState<string>();
  const [searched, setSearched] = useState(false);

  const load = useCallback(async () => {
    setFailure(undefined);
    try {
      const [nextRoles, nextSaved, nextHistory] = await Promise.all([
        getRoles({ limit: 30 }),
        getSavedRoles(),
        getReadinessHistory(),
      ]);
      setRoles(nextRoles.data);
      setSavedRoles(nextSaved.data);
      setHistory(nextHistory.data);
      setActiveAnalysis(nextHistory.data[0]);
      setSelectedRoleIds(
        nextSaved.data.slice(0, 3).map((item) => item.role.id),
      );
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "Role Explorer could not be loaded."),
      );
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  const roleById = useMemo(() => {
    const values = new Map<string, Role>();
    for (const role of roles ?? []) values.set(role.id, role);
    for (const saved of savedRoles ?? []) values.set(saved.role.id, saved.role);
    for (const entry of comparison?.entries ?? [])
      values.set(entry.role.id, entry.role);
    return values;
  }, [comparison?.entries, roles, savedRoles]);

  async function searchRoles(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyKey("search");
    setFailure(undefined);
    setSearched(true);
    try {
      const page = await getRoles({ limit: 30, q: query.trim(), seniority });
      setRoles(page.data);
    } catch (error) {
      setFailure(requestErrorMessage(error, "Role search failed."));
    } finally {
      setBusyKey(undefined);
    }
  }

  async function saveTarget(role: Role) {
    setBusyKey(`save-${role.id}`);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const saved = await saveRole({ notes: null, roleId: role.id });
      setSavedRoles((current = []) => {
        const present = current.some((item) => item.id === saved.id);
        return present
          ? current.map((item) => (item.id === saved.id ? saved : item))
          : [saved, ...current];
      });
      setSuccess(`${role.title} saved.`);
    } catch (error) {
      setFailure(requestErrorMessage(error, "The role could not be saved."));
    } finally {
      setBusyKey(undefined);
    }
  }

  async function saveNotes(
    event: FormEvent<HTMLFormElement>,
    savedRole: SavedRole,
  ) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const notes = String(form.get("notes") ?? "").trim() || null;
    setBusyKey(`notes-${savedRole.id}`);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const updated = await updateSavedRole(savedRole, { notes });
      setSavedRoles((current = []) =>
        current.map((item) => (item.id === savedRole.id ? updated : item)),
      );
      setSuccess(`${updated.role.title} notes saved.`);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "Saved role notes could not be updated."),
      );
    } finally {
      setBusyKey(undefined);
    }
  }

  async function removeSavedRole(savedRole: SavedRole) {
    setBusyKey(`delete-${savedRole.id}`);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      await deleteSavedRole(savedRole);
      setSavedRoles((current = []) =>
        current.filter((item) => item.id !== savedRole.id),
      );
      setSelectedRoleIds((current) =>
        current.filter((id) => id !== savedRole.role.id),
      );
      setSuccess(`${savedRole.role.title} removed from saved roles.`);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "The saved role could not be removed."),
      );
    } finally {
      setBusyKey(undefined);
    }
  }

  async function runAnalysis(target: {
    roleId?: string;
    savedRoleId?: string;
    title: string;
  }) {
    setBusyKey(`analysis-${target.roleId ?? target.savedRoleId}`);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      const analysis = await analyzeRole(
        target.roleId
          ? { roleId: target.roleId }
          : { savedRoleId: target.savedRoleId ?? null },
      );
      setActiveAnalysis(analysis);
      setHistory((current) => [
        analysis,
        ...current.filter((item) => item.id !== analysis.id),
      ]);
      setSuccess(`${target.title} readiness analyzed.`);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "Role readiness could not be analyzed."),
      );
    } finally {
      setBusyKey(undefined);
    }
  }

  function toggleCompare(roleId: string) {
    setSelectedRoleIds((current) => {
      if (current.includes(roleId))
        return current.filter((id) => id !== roleId);
      return [...current, roleId].slice(0, 3);
    });
  }

  async function runComparison() {
    setBusyKey("compare");
    setFailure(undefined);
    try {
      setComparison(await compareRoles(selectedRoleIds));
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "Role comparison could not be loaded."),
      );
    } finally {
      setBusyKey(undefined);
    }
  }

  if ((!roles || !savedRoles) && failure) {
    return (
      <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={failure}
          onRetry={() => void load()}
          title="Role Explorer unavailable"
        />
      </main>
    );
  }

  if (!roles || !savedRoles) {
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
        description="Compare your demonstrated, evidence-backed capabilities with a reusable target role. This is role readiness—not a job-specific match or an employer score."
        eyebrow="Role Explorer"
        title="Role readiness"
      />

      {failure && (
        <Alert title="Role Explorer unavailable" tone="danger">
          {failure}
        </Alert>
      )}
      {success && (
        <Alert title="Saved" tone="success">
          {success}
        </Alert>
      )}

      <form
        className="grid gap-3 rounded-lg border border-line bg-surface p-4 shadow-sm md:grid-cols-[minmax(0,1fr)_12rem_auto]"
        onSubmit={(event) => void searchRoles(event)}
      >
        <label className="text-sm font-bold text-foreground">
          Search roles
          <input
            className="mt-1 min-h-11 w-full rounded-xl border border-line px-3.5 text-sm outline-none focus:border-primary focus:ring-3 focus:ring-primary-soft"
            maxLength={160}
            name="query"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Product manager, software engineer, data analyst"
            type="search"
            value={query}
          />
        </label>
        <label className="text-sm font-bold text-foreground">
          Seniority
          <Select
            className="mt-1"
            onChange={(event) =>
              setSeniority(event.target.value as RoleSeniority | "")
            }
            value={seniority}
          >
            {seniorities.map((item) => (
              <option key={item.value || "any"} value={item.value}>
                {item.label}
              </option>
            ))}
          </Select>
        </label>
        <Button
          className="self-end"
          loading={busyKey === "search"}
          type="submit"
        >
          <Search aria-hidden="true" className="size-4" />
          Search
        </Button>
      </form>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <section aria-labelledby="role-results" className="space-y-4">
          <h2 className="text-lg font-black text-foreground" id="role-results">
            Matching roles
          </h2>
          {roles.length === 0 ? (
            <EmptyState
              description={
                searched
                  ? "No role matched the current filters."
                  : "Seed roles will appear here when available."
              }
              title="No matching roles"
            />
          ) : (
            <div className="grid gap-3 lg:grid-cols-2">
              {roles.map((role) => {
                const saved = savedForRole(savedRoles, role.id);
                const selected = selectedRoleIds.includes(role.id);
                return (
                  <article
                    className="rounded-lg border border-line bg-surface p-4 shadow-sm"
                    key={role.id}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="font-black text-foreground">
                          {role.title}
                        </h3>
                        <p className="mt-1 text-sm text-muted">
                          {label(role.seniority)} | {role.industry} |{" "}
                          {role.domain}
                        </p>
                      </div>
                      <Badge tone={saved ? "success" : "neutral"}>
                        {saved ? "Saved" : "Available"}
                      </Badge>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-muted">
                      {role.description}
                    </p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button
                        disabled={Boolean(saved)}
                        loading={busyKey === `save-${role.id}`}
                        onClick={() => void saveTarget(role)}
                        variant="secondary"
                      >
                        <Bookmark aria-hidden="true" className="size-4" />
                        Save
                      </Button>
                      <Button
                        loading={busyKey === `analysis-${role.id}`}
                        onClick={() =>
                          void runAnalysis({
                            roleId: role.id,
                            title: role.title,
                          })
                        }
                      >
                        <Target aria-hidden="true" className="size-4" />
                        Analyze
                      </Button>
                      <Button
                        aria-pressed={selected}
                        onClick={() => toggleCompare(role.id)}
                        variant={selected ? "dark" : "ghost"}
                      >
                        {selected ? (
                          <Check aria-hidden="true" className="size-4" />
                        ) : (
                          <GitCompare aria-hidden="true" className="size-4" />
                        )}
                        Compare
                      </Button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <aside aria-labelledby="saved-roles" className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-black text-foreground" id="saved-roles">
              Saved roles
            </h2>
            <Button
              disabled={selectedRoleIds.length < 2}
              loading={busyKey === "compare"}
              onClick={() => void runComparison()}
              variant="secondary"
            >
              <GitCompare aria-hidden="true" className="size-4" />
              Compare selected
            </Button>
          </div>
          {savedRoles.length === 0 ? (
            <EmptyState
              className="min-h-56"
              description="Saved roles will appear here."
              title="No saved roles"
            />
          ) : (
            <div className="space-y-3">
              {savedRoles.map((savedRole) => (
                <article
                  className="rounded-lg border border-line bg-surface p-4 shadow-sm"
                  key={savedRole.id}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-black text-foreground">
                        {savedRole.role.title}
                      </h3>
                      <p className="mt-1 text-xs font-semibold text-muted">
                        Version {savedRole.version}
                      </p>
                    </div>
                    <input
                      aria-label={`Compare ${savedRole.role.title}`}
                      checked={selectedRoleIds.includes(savedRole.role.id)}
                      className="mt-1 size-4 accent-primary"
                      onChange={() => toggleCompare(savedRole.role.id)}
                      type="checkbox"
                    />
                  </div>
                  <form
                    className="mt-3 space-y-2"
                    onSubmit={(event) => void saveNotes(event, savedRole)}
                  >
                    <label
                      className="block text-xs font-bold text-foreground"
                      htmlFor={`notes-${savedRole.id}`}
                    >
                      Notes
                    </label>
                    <textarea
                      className="min-h-20 w-full rounded-lg border border-line p-3 text-sm outline-none focus:border-primary focus:ring-3 focus:ring-primary-soft"
                      defaultValue={savedRole.notes ?? ""}
                      id={`notes-${savedRole.id}`}
                      maxLength={1_000}
                      name="notes"
                    />
                    <div className="flex flex-wrap gap-2">
                      <Button
                        loading={busyKey === `notes-${savedRole.id}`}
                        type="submit"
                        variant="secondary"
                      >
                        <Save aria-hidden="true" className="size-4" />
                        Save notes
                      </Button>
                      <Button
                        loading={busyKey === `analysis-${savedRole.id}`}
                        onClick={() =>
                          void runAnalysis({
                            savedRoleId: savedRole.id,
                            title: savedRole.role.title,
                          })
                        }
                      >
                        <Target aria-hidden="true" className="size-4" />
                        Analyze
                      </Button>
                      <Button
                        loading={busyKey === `delete-${savedRole.id}`}
                        onClick={() => void removeSavedRole(savedRole)}
                        variant="danger"
                      >
                        <Trash2 aria-hidden="true" className="size-4" />
                        Remove
                      </Button>
                    </div>
                  </form>
                </article>
              ))}
            </div>
          )}
        </aside>
      </div>

      <section aria-labelledby="readiness-results" className="space-y-4">
        <h2
          className="text-lg font-black text-foreground"
          id="readiness-results"
        >
          Readiness results
        </h2>
        {!activeAnalysis ? (
          <EmptyState
            description="Analyses will appear here after readiness is calculated."
            title="No readiness analysis"
          />
        ) : (
          <ReadinessPanel analysis={activeAnalysis} />
        )}
      </section>

      {comparison && (
        <section aria-labelledby="role-comparison" className="space-y-4">
          <h2
            className="text-lg font-black text-foreground"
            id="role-comparison"
          >
            Role comparison
          </h2>
          <div className="grid gap-3 lg:grid-cols-3">
            {comparison.entries.map((entry) => (
              <article
                className="rounded-lg border border-line bg-surface p-4 shadow-sm"
                key={entry.role.id}
              >
                <h3 className="font-black text-foreground">
                  {entry.role.title}
                </h3>
                <p className="mt-1 text-sm text-muted">
                  {roleById.get(entry.role.id)?.domain}
                </p>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <Metric
                    label="Score"
                    value={entry.latestAnalysis?.displayScore ?? "None"}
                  />
                  <Metric
                    label="Demonstrated"
                    value={entry.demonstratedCount}
                  />
                  <Metric
                    label="Required gaps"
                    value={entry.requiredGapCount}
                  />
                  <Metric
                    label="Evidence links"
                    value={entry.strongestEvidenceCount}
                  />
                </dl>
              </article>
            ))}
          </div>
          <p className="text-sm text-muted">{comparison.scoringDisclaimer}</p>
        </section>
      )}

      {history.length > 0 && (
        <section aria-labelledby="readiness-history" className="space-y-4">
          <h2
            className="text-lg font-black text-foreground"
            id="readiness-history"
          >
            Readiness history
          </h2>
          <div className="data-region table-scroll">
            <table className="min-w-full divide-y divide-line text-sm">
              <caption className="sr-only">
                Recent role readiness analyses
              </caption>
              <thead className="bg-surface-subtle text-left text-xs uppercase text-muted">
                <tr>
                  <th className="px-4 py-3" scope="col">
                    Role
                  </th>
                  <th className="px-4 py-3" scope="col">
                    Score
                  </th>
                  <th className="px-4 py-3" scope="col">
                    Label
                  </th>
                  <th className="px-4 py-3" scope="col">
                    Created
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {history.map((item) => (
                  <tr
                    className={cn(
                      "cursor-pointer hover:bg-surface-subtle",
                      activeAnalysis?.id === item.id && "bg-primary-soft/50",
                    )}
                    key={item.id}
                    onClick={() => setActiveAnalysis(item)}
                  >
                    <td className="px-4 py-3 font-semibold text-foreground">
                      {item.role.title}
                    </td>
                    <td className="px-4 py-3">
                      {item.displayScore ?? "Not scored"}
                    </td>
                    <td className="px-4 py-3">{label(item.readinessLabel)}</td>
                    <td className="px-4 py-3">
                      {new Date(item.createdAt).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}

function Metric({
  label: metricLabel,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div>
      <dt className="text-xs font-bold uppercase text-muted">{metricLabel}</dt>
      <dd className="mt-1 font-black text-foreground">{value}</dd>
    </div>
  );
}

function ReadinessPanel({ analysis }: { analysis: RoleReadiness }) {
  const score = analysis.displayScore;
  const demonstrated = analysis.competencies.filter(
    (item) => item.matchState === "demonstrated",
  ).length;
  const gaps = analysis.competencies.filter(
    (item) => item.matchState === "missing" || item.matchState === "unknown",
  );
  return (
    <div className="rounded-lg border border-line bg-surface p-4 shadow-sm">
      <div className="grid gap-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <div>
          <p className="text-sm font-bold text-muted">{analysis.role.title}</p>
          <h3 className="mt-1 text-xl font-black text-foreground">
            {score === null ? "Insufficient data" : `${score}/100`}
          </h3>
          {score !== null && (
            <div className="mt-4">
              <ScoreBar
                label="Role readiness"
                score={score}
                tone={scoreTone(score)}
              />
            </div>
          )}
          <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
            <Metric label="Demonstrated" value={demonstrated} />
            <Metric label="Gaps" value={gaps.length} />
          </dl>
        </div>
        <div>
          <p className="text-sm leading-6 text-foreground">
            {analysis.summary}
          </p>
          <p className="mt-3 text-sm text-muted">
            {analysis.scoringDisclaimer}
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {analysis.components.map((component) => (
              <ScoreBar
                key={component.dimension}
                label={label(component.dimension)}
                score={Math.round(component.scoreBasisPoints / 100)}
                tone={scoreTone(Math.round(component.scoreBasisPoints / 100))}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="data-region table-scroll mt-6">
        <table className="min-w-full divide-y divide-line text-sm">
          <caption className="sr-only">
            Requirement to evidence readiness results
          </caption>
          <thead className="bg-surface-subtle text-left text-xs uppercase text-muted">
            <tr>
              <th className="px-4 py-3" scope="col">
                Requirement
              </th>
              <th className="px-4 py-3" scope="col">
                State
              </th>
              <th className="px-4 py-3" scope="col">
                Evidence
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {analysis.competencies.map((item) => (
              <tr key={item.id}>
                <th
                  className="px-4 py-3 text-left font-semibold text-foreground"
                  scope="row"
                >
                  {item.label}
                  <span className="mt-1 block text-xs font-normal text-muted">
                    {label(item.dimension)} | {label(item.importance)}
                  </span>
                </th>
                <td className="px-4 py-3">
                  <Badge
                    tone={
                      item.matchState === "demonstrated" ? "success" : "neutral"
                    }
                  >
                    {label(item.matchState)}
                  </Badge>
                  <p className="mt-2 max-w-sm text-xs leading-5 text-muted">
                    {item.explanation}
                  </p>
                </td>
                <td className="px-4 py-3">
                  {item.evidence.length === 0 ? (
                    <span className="text-muted">None</span>
                  ) : (
                    <ul className="space-y-2">
                      {item.evidence.map((link) => (
                        <li key={link.id}>
                          <p className="font-semibold text-foreground">
                            {link.evidenceTitle}
                          </p>
                          <p className="text-xs text-muted">
                            {label(link.evidenceStrength)} evidence
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function RoleExplorerLoading() {
  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
      <LoadingSkeleton />
    </main>
  );
}

export function RoleExplorerRouteError({ reset }: { reset: () => void }) {
  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
      <ErrorState
        description="Role readiness could not be displayed. No career record was changed."
        onRetry={reset}
        title="Role Explorer unavailable"
      />
    </main>
  );
}
