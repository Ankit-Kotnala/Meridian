"use client";

import {
  Award,
  ChevronLeft,
  ChevronRight,
  Filter,
  Plus,
  RefreshCcw,
  Search,
} from "lucide-react";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";

import {
  Alert,
  Button,
  Card,
  CheckboxField,
  EmptyState,
  ErrorState,
  FieldLabel,
  Input,
  LoadingSkeleton,
  Select,
  buttonStyles,
  cn,
} from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  createEvidence,
  getEvidence,
  getExperiences,
  getSkills,
} from "../api/career-vault-api";
import type {
  EvidenceFilters,
  EvidenceInput,
  EvidenceItem,
  EvidenceState,
  Experience,
  Page,
  Skill,
} from "../api/types";
import { EvidenceStateBadge } from "../components/evidence-semantics";
import { EvidenceForm } from "../components/evidence-form";
import { FieldErrorSummary } from "../components/form-controls";
import {
  validateEvidence,
  type FieldErrors,
} from "../validation/career-vault-validation";

function date(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
    new Date(value),
  );
}

function EvidenceSummary({ evidence }: { evidence: EvidenceItem }) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-extrabold text-foreground">{evidence.title}</h3>
          <p className="mt-1 text-xs capitalize text-muted">{evidence.type}</p>
        </div>
        <EvidenceStateBadge state={evidence.state} />
      </div>
      <p className="mt-3 line-clamp-3 text-sm leading-6 text-muted">
        {evidence.description}
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <div>
          <dt className="font-bold text-muted">Factual use</dt>
          <dd className="mt-1 font-extrabold">
            {evidence.factualEligible ? "Eligible" : "Not eligible"}
          </dd>
        </div>
        <div>
          <dt className="font-bold text-muted">Numeric use</dt>
          <dd className="mt-1 font-extrabold">
            {evidence.numericEligible ? "Eligible" : "Not eligible"}
          </dd>
        </div>
      </dl>
      <div className="mt-auto flex items-center justify-between gap-3 border-t border-line pt-4 text-xs text-muted">
        <span>Updated {date(evidence.updatedAt)}</span>
        <Link
          className="font-extrabold text-primary"
          href={`/evidence/${encodeURIComponent(evidence.id)}`}
        >
          Review details
        </Link>
      </div>
    </div>
  );
}

export function EvidenceVaultView() {
  const [page, setPage] = useState<Page<EvidenceItem>>();
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [query, setQuery] = useState("");
  const [state, setState] = useState<EvidenceState | "">("");
  const [archived, setArchived] = useState(false);
  const [after, setAfter] = useState<string>();
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [loading, setLoading] = useState(false);
  const errorRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    setFailure(undefined);
    try {
      const filters: EvidenceFilters = {
        ...(after ? { after } : {}),
        ...(archived ? { archived: true } : {}),
        ...(query ? { query } : {}),
        ...(state ? { state } : {}),
      };
      const [nextPage, nextExperiences, nextSkills] = await Promise.all([
        getEvidence(filters),
        getExperiences(),
        getSkills(),
      ]);
      setPage(nextPage);
      setExperiences(nextExperiences);
      setSkills(nextSkills);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t load your Evidence Vault."),
      );
    }
  }, [after, archived, query, state]);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setQuery(String(form.get("query") ?? "").trim());
    setState(String(form.get("state") ?? "") as EvidenceState | "");
    setArchived(form.get("archived") === "on");
    setAfter(undefined);
    setCursorHistory([]);
  }

  async function saveEvidence(input: EvidenceInput) {
    const nextErrors = validateEvidence(input);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      queueMicrotask(() => errorRef.current?.focus());
      return;
    }
    setLoading(true);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      await createEvidence(input);
      setShowCreate(false);
      setErrors({});
      setSuccess(
        "Evidence saved. Its server-authoritative eligibility is shown after review and confirmation.",
      );
      await load();
    } catch (error) {
      setFailure(requestErrorMessage(error, "We couldn’t save this evidence."));
    } finally {
      setLoading(false);
    }
  }

  if (!page && !failure) {
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <LoadingSkeleton />
      </main>
    );
  }
  if (!page) {
    return (
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={failure ?? "Evidence Vault could not be loaded."}
          onRetry={load}
          title="Evidence Vault unavailable"
        />
      </main>
    );
  }

  const filtered = Boolean(query || state || archived || after);
  return (
    <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
      <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow">Owned sources and proof</p>
          <h1 className="mt-2 text-2xl font-black tracking-[-0.035em] sm:text-3xl">
            Evidence Vault
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Store provenance-rich career evidence. State, confirmation,
            extraction confidence, and generation eligibility remain separate.
          </p>
        </div>
        <Button
          onClick={() => {
            setShowCreate(true);
            setErrors({});
          }}
        >
          <Plus aria-hidden="true" className="size-4" /> Add evidence
        </Button>
      </header>

      {failure && (
        <Alert className="mb-5" title="Evidence not changed" tone="danger">
          {failure}
        </Alert>
      )}
      {success && (
        <Alert className="mb-5" title="Evidence saved" tone="success">
          {success}
        </Alert>
      )}

      {showCreate && (
        <Card
          className="mb-6 p-5 sm:p-6"
          aria-labelledby="add-evidence-heading"
        >
          <h2 className="text-lg font-extrabold" id="add-evidence-heading">
            Add evidence manually
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted">
            New evidence is not automatically verified or numerically eligible.
            The server applies evidence policy after explicit actions.
          </p>
          <div className="mt-5">
            <FieldErrorSummary errors={errors} ref={errorRef} />
            <EvidenceForm
              errors={errors}
              experiences={experiences}
              loading={loading}
              onCancel={() => setShowCreate(false)}
              onSubmit={(value) => void saveEvidence(value)}
              skills={skills}
            />
          </div>
        </Card>
      )}

      <Card className="mb-5 p-4 sm:p-5">
        <form
          className="grid gap-4 md:grid-cols-[1fr_12rem_auto_auto] md:items-end"
          onSubmit={applyFilters}
        >
          <div className="space-y-2">
            <FieldLabel htmlFor="evidence-search">
              Search your evidence
            </FieldLabel>
            <div className="relative">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-3.5 size-4 text-muted"
              />
              <Input
                className="pl-9"
                defaultValue={query}
                id="evidence-search"
                maxLength={200}
                name="query"
                placeholder="Title, skill, or organization"
              />
            </div>
          </div>
          <div className="space-y-2">
            <FieldLabel htmlFor="evidence-state-filter">
              Evidence state
            </FieldLabel>
            <Select
              defaultValue={state}
              id="evidence-state-filter"
              name="state"
            >
              <option value="">All states</option>
              <option value="verified">Verified</option>
              <option value="confirmed">Confirmed</option>
              <option value="supported">Supported</option>
              <option value="inferred">Inferred</option>
              <option value="unsupported">Unsupported</option>
            </Select>
          </div>
          <CheckboxField
            defaultChecked={archived}
            id="evidence-archived-filter"
            label="Show archived"
            name="archived"
          />
          <Button type="submit" variant="secondary">
            <Filter aria-hidden="true" className="size-4" /> Apply filters
          </Button>
        </form>
      </Card>

      {page.data.length === 0 ? (
        <EmptyState
          action={
            filtered ? (
              <Button
                onClick={() => {
                  setQuery("");
                  setState("");
                  setArchived(false);
                  setAfter(undefined);
                  setCursorHistory([]);
                }}
                variant="secondary"
              >
                Clear filters
              </Button>
            ) : undefined
          }
          description={
            filtered
              ? "No owned evidence matches the current filters."
              : "Add evidence manually or capture an achievement. A resume is not required."
          }
          title={
            filtered ? "No matching evidence" : "Your Evidence Vault is empty"
          }
        />
      ) : (
        <>
          <div className="grid gap-4 md:hidden" aria-label="Evidence results">
            {page.data.map((evidence) => (
              <Card className="p-5" key={evidence.id}>
                <EvidenceSummary evidence={evidence} />
              </Card>
            ))}
          </div>
          <div className="hidden overflow-x-auto rounded-2xl border border-line bg-white shadow-sm md:block">
            <table className="w-full border-collapse text-left text-sm">
              <caption className="sr-only">
                Evidence Vault results and generation eligibility
              </caption>
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-5 py-4" scope="col">
                    Evidence
                  </th>
                  <th className="px-5 py-4" scope="col">
                    State
                  </th>
                  <th className="px-5 py-4" scope="col">
                    Factual use
                  </th>
                  <th className="px-5 py-4" scope="col">
                    Numeric use
                  </th>
                  <th className="px-5 py-4" scope="col">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {page.data.map((evidence) => (
                  <tr key={evidence.id}>
                    <th className="px-5 py-4 font-extrabold" scope="row">
                      <span className="block">{evidence.title}</span>
                      <span className="mt-1 block text-xs font-normal text-muted">
                        Updated {date(evidence.updatedAt)}
                      </span>
                    </th>
                    <td className="px-5 py-4">
                      <EvidenceStateBadge state={evidence.state} />
                    </td>
                    <td className="px-5 py-4 font-bold">
                      {evidence.factualEligible ? "Eligible" : "Not eligible"}
                    </td>
                    <td className="px-5 py-4 font-bold">
                      {evidence.numericEligible ? "Eligible" : "Not eligible"}
                    </td>
                    <td className="px-5 py-4 text-right">
                      <Link
                        className="font-extrabold text-primary"
                        href={`/evidence/${encodeURIComponent(evidence.id)}`}
                      >
                        Review
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <nav
        aria-label="Evidence pages"
        className="mt-5 flex items-center justify-between gap-3"
      >
        <Button
          disabled={cursorHistory.length === 0}
          onClick={() => {
            const previous = cursorHistory.at(-1);
            setCursorHistory((current) => current.slice(0, -1));
            setAfter(previous || undefined);
          }}
          variant="secondary"
        >
          <ChevronLeft aria-hidden="true" className="size-4" /> Previous
        </Button>
        <span className="text-xs text-muted">
          Page {cursorHistory.length + 1}
        </span>
        <Button
          disabled={!page.page.hasMore || !page.page.nextCursor}
          onClick={() => {
            setCursorHistory((current) => [...current, after ?? ""]);
            setAfter(page.page.nextCursor ?? undefined);
          }}
          variant="secondary"
        >
          Next <ChevronRight aria-hidden="true" className="size-4" />
        </Button>
      </nav>

      <div className="mt-6 flex flex-wrap gap-3">
        <Link
          className={cn(buttonStyles.base, buttonStyles.secondary)}
          href="/achievement-inbox"
        >
          <Award aria-hidden="true" className="size-4" /> Achievement Inbox
        </Link>
        <Button onClick={() => void load()} variant="ghost">
          <RefreshCcw aria-hidden="true" className="size-4" /> Refresh
        </Button>
      </div>
    </main>
  );
}
