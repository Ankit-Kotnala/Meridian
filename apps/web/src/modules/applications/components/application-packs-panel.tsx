"use client";

import {
  FileCheck2,
  FilePlus2,
  RefreshCcw,
  ShieldCheck,
  Trash2,
} from "lucide-react";
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
  Badge,
  Button,
  CheckboxField,
  ConfirmDialog,
  EmptyState,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  deleteApplicationDocument,
  generateApplicationPack,
  getApplicationConsistency,
  getApplicationPack,
  listApplicationPacks,
} from "../api/applications-api";
import type {
  ApplicationConsistency,
  ApplicationDetail,
  ApplicationDocument,
  ApplicationDocumentKind,
  ApplicationPack,
  ApplicationPackSummary,
} from "../api/types";
import {
  consistencyTone,
  documentKinds,
  formatDateTime,
  humanize,
} from "./application-options";

type NoticeHandlers = {
  onFailure: (message: string, conflict: boolean) => void;
  onSuccess: (message: string) => void;
};

type PackPageState = {
  error: string | null;
  hasMore: boolean;
  items: ApplicationPackSummary[];
  nextCursor: string | null;
  status: "idle" | "pending" | "success" | "error";
};

function initialPackPageState(): PackPageState {
  return {
    error: null,
    hasMore: false,
    items: [],
    nextCursor: null,
    status: "idle",
  };
}

type PackDetailState =
  | { status: "pending" }
  | { message: string; status: "error" }
  | { pack: ApplicationPack; status: "success" };

function mergePacks(
  current: ApplicationPackSummary[],
  incoming: ApplicationPackSummary[],
  append: boolean,
): ApplicationPackSummary[] {
  const currentById = new Map(current.map((pack) => [pack.id, pack]));
  if (append) {
    return [
      ...current,
      ...incoming.filter((pack) => !currentById.has(pack.id)),
    ];
  }
  const incomingIds = new Set(incoming.map((pack) => pack.id));
  return [
    ...incoming.map((pack) => currentById.get(pack.id) ?? pack),
    ...current.filter((pack) => !incomingIds.has(pack.id)),
  ];
}

export function ApplicationPacksPanel({
  application,
  onFailure,
  onMarkApplied,
  onPackCountChange,
  onSuccess,
  reloadEpoch,
}: {
  application: ApplicationDetail;
  onMarkApplied?: () => void;
  onPackCountChange: (delta: number) => void;
  reloadEpoch: number;
} & NoticeHandlers) {
  const [packs, setPacks] = useState<PackPageState>(initialPackPageState);
  const [packDetails, setPackDetails] = useState<
    Record<string, PackDetailState>
  >({});
  const [consistency, setConsistency] = useState<
    Record<string, ApplicationConsistency>
  >({});
  const [busyKey, setBusyKey] = useState<string>();
  const [deleteTarget, setDeleteTarget] = useState<{
    document: ApplicationDocument;
    packId: string;
  }>();
  const listRequest = useRef(0);
  const detailRequests = useRef(new Map<string, number>());
  const packIdempotencyKey = useRef<string | undefined>(undefined);

  /**
   * Most recent generated "assisted apply handoff" document — the deep link
   * plus pre-filled answers the user opens to submit in their own session
   * (ADR 0019 §4). Surfaced prominently rather than buried in the generic
   * document list below, since this is the one document most people came here
   * for after clicking "Apply for me" on a job.
   */
  const latestHandoff = useMemo(() => {
    for (const summary of packs.items) {
      const detail = packDetails[summary.id];
      if (detail?.status !== "success") continue;
      const document = detail.pack.documents.find(
        (item) => item.kind === "assisted_apply_handoff" && !item.deletedAt,
      );
      if (document) return { document, packId: detail.pack.id };
    }
    return null;
  }, [packDetails, packs.items]);

  const loadPacks = useCallback(
    async (cursor?: string) => {
      const requestId = ++listRequest.current;
      setPacks((current) => ({
        ...current,
        error: null,
        status: "pending",
      }));
      try {
        const page = await listApplicationPacks(application.id, {
          ...(cursor ? { cursor } : {}),
          limit: 25,
        });
        if (requestId !== listRequest.current) return;
        setPacks((current) => ({
          error: null,
          hasMore: page.page.hasMore,
          items: mergePacks(current.items, page.data, Boolean(cursor)),
          nextCursor: page.page.nextCursor,
          status: "success",
        }));
      } catch (error) {
        if (requestId !== listRequest.current) return;
        setPacks((current) => ({
          ...current,
          error: requestErrorMessage(
            error,
            "Application packs could not be loaded.",
          ),
          status: "error",
        }));
      }
    },
    [application.id],
  );

  const loadPackDetails = useCallback(async (packId: string) => {
    const requestId = (detailRequests.current.get(packId) ?? 0) + 1;
    detailRequests.current.set(packId, requestId);
    setPackDetails((current) => ({
      ...current,
      [packId]: { status: "pending" },
    }));
    try {
      const pack = await getApplicationPack(packId);
      if (detailRequests.current.get(packId) !== requestId) return;
      setPackDetails((current) => ({
        ...current,
        [packId]: { pack, status: "success" },
      }));
      setPacks((current) => ({
        ...current,
        items: current.items.map((item) => (item.id === pack.id ? pack : item)),
      }));
    } catch (error) {
      if (detailRequests.current.get(packId) !== requestId) return;
      setPackDetails((current) => ({
        ...current,
        [packId]: {
          message: requestErrorMessage(
            error,
            "Generated documents could not be loaded.",
          ),
          status: "error",
        },
      }));
    }
  }, []);

  useEffect(() => {
    let active = true;
    const requests = detailRequests.current;
    queueMicrotask(() => {
      if (!active) return;
      setPacks(initialPackPageState());
      setPackDetails({});
      setConsistency({});
      setDeleteTarget(undefined);
      void loadPacks();
    });
    return () => {
      active = false;
      listRequest.current += 1;
      requests.clear();
    };
  }, [loadPacks, reloadEpoch]);

  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const includeKinds = form
      .getAll("includeKinds")
      .map(String) as ApplicationDocumentKind[];
    if (!includeKinds.length) {
      onFailure(
        "Choose at least one document for this application pack.",
        false,
      );
      return;
    }
    setBusyKey("generate");
    try {
      packIdempotencyKey.current ??= crypto.randomUUID();
      const pack = await generateApplicationPack(
        application.id,
        {
          includeKinds,
        },
        packIdempotencyKey.current,
      );
      setPacks((current) => ({
        ...current,
        items: [pack, ...current.items.filter((item) => item.id !== pack.id)],
        status: current.status === "idle" ? "success" : current.status,
      }));
      setPackDetails((current) => ({
        ...current,
        [pack.id]: { pack, status: "success" },
      }));
      packIdempotencyKey.current = crypto.randomUUID();
      onPackCountChange(1);
      onSuccess(
        pack.status === "blocked"
          ? "The pack was checked and blocked because consistency requirements were not met."
          : "Application pack generated from the pinned job, resume, claims, and evidence.",
      );
    } catch (error) {
      onFailure(
        requestErrorMessage(
          error,
          "The application pack could not be generated.",
        ),
        false,
      );
    } finally {
      setBusyKey(undefined);
    }
  }

  async function refreshPack(packId: string) {
    setBusyKey(`pack-${packId}`);
    try {
      const [pack, check] = await Promise.all([
        getApplicationPack(packId),
        getApplicationConsistency(packId),
      ]);
      setPacks((current) => ({
        ...current,
        items: current.items.map((item) => (item.id === pack.id ? pack : item)),
      }));
      setPackDetails((current) => ({
        ...current,
        [pack.id]: { pack, status: "success" },
      }));
      setConsistency((current) => ({ ...current, [packId]: check }));
      onSuccess("Pack and consistency findings refreshed.");
    } catch (error) {
      onFailure(
        requestErrorMessage(
          error,
          "The application pack could not be refreshed.",
        ),
        false,
      );
    } finally {
      setBusyKey(undefined);
    }
  }

  async function removeDocument() {
    if (!deleteTarget) return;
    setBusyKey(`delete-${deleteTarget.document.id}`);
    try {
      await deleteApplicationDocument(application.id, deleteTarget.document.id);
      setPackDetails((current) => {
        const state = current[deleteTarget.packId];
        if (state?.status !== "success") return current;
        return {
          ...current,
          [deleteTarget.packId]: {
            pack: {
              ...state.pack,
              documents: state.pack.documents.filter(
                (document) => document.id !== deleteTarget.document.id,
              ),
            },
            status: "success",
          },
        };
      });
      setDeleteTarget(undefined);
      onSuccess("Generated document deleted.");
    } catch (error) {
      onFailure(
        requestErrorMessage(error, "The document could not be deleted."),
        false,
      );
    } finally {
      setBusyKey(undefined);
    }
  }

  return (
    <div className="space-y-6">
      {latestHandoff && application.stage !== "applied" && (
        <section
          aria-labelledby="assisted-apply-heading"
          className="rounded-xl border border-primary/40 bg-primary-soft/40 p-4 shadow-sm sm:p-5"
        >
          <div className="flex items-center gap-2">
            <FileCheck2 aria-hidden="true" className="size-5 text-primary" />
            <h2
              className="text-lg font-black text-foreground"
              id="assisted-apply-heading"
            >
              Ready to submit
            </h2>
          </div>
          <p className="mt-2 text-sm text-muted">
            Rezumi assembled this from your tailored resume and Application
            Profile. Open the job posting and submit it yourself in your own
            browser session — Rezumi never submits on your behalf.
          </p>
          <div className="mt-3 rounded-xl bg-surface p-4">
            <p className="whitespace-pre-wrap text-sm leading-6 text-foreground">
              {latestHandoff.document.body}
            </p>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button disabled={!onMarkApplied} onClick={() => onMarkApplied?.()}>
              I applied
            </Button>
          </div>
        </section>
      )}

      <section
        aria-labelledby="generate-pack-heading"
        className="rounded-xl border border-line bg-surface p-4 shadow-sm sm:p-5"
      >
        <div className="flex items-center gap-2">
          <FilePlus2 aria-hidden="true" className="size-5 text-primary" />
          <h2
            className="text-lg font-black text-foreground"
            id="generate-pack-heading"
          >
            Generate an application pack
          </h2>
        </div>
        <p className="mt-2 text-sm text-muted">
          Select only the drafts you need. Every factual claim must resolve to
          eligible evidence pinned to resume version{" "}
          {application.resumeVersionNumber}. Generated documents are drafts;
          Rezumi does not submit or send them.
        </p>
        <form
          className="mt-4"
          onChange={() => {
            packIdempotencyKey.current = crypto.randomUUID();
          }}
          onSubmit={(event) => void generate(event)}
        >
          <fieldset>
            <legend className="text-sm font-black text-foreground">
              Documents to generate
            </legend>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {documentKinds.map((kind) => (
                <CheckboxField
                  defaultChecked={
                    kind === "tailored_resume" || kind === "cover_letter"
                  }
                  id={`document-kind-${kind}`}
                  key={kind}
                  label={humanize(kind)}
                  name="includeKinds"
                  value={kind}
                />
              ))}
            </div>
          </fieldset>
          <Button
            className="mt-4"
            loading={busyKey === "generate"}
            type="submit"
          >
            <ShieldCheck aria-hidden="true" className="size-4" />
            Generate grounded drafts
          </Button>
        </form>
      </section>

      {packs.status === "pending" && packs.items.length === 0 && (
        <p className="text-sm text-muted" role="status">
          Loading application packs...
        </p>
      )}
      {packs.error && (
        <Alert title="Application packs unavailable" tone="danger">
          <p>{packs.error}</p>
          <Button
            className="mt-3 min-h-9 px-3"
            onClick={() =>
              void loadPacks(
                packs.items.length
                  ? (packs.nextCursor ?? undefined)
                  : undefined,
              )
            }
            variant="secondary"
          >
            Retry application packs
          </Button>
        </Alert>
      )}
      {packs.items.length ? (
        <div className="space-y-5">
          {packs.items.map((pack) => {
            const check = consistency[pack.id];
            const findings = check?.findings ?? pack.consistencyFindings;
            const status = check?.status ?? pack.consistencyStatus;
            const detailState = packDetails[pack.id];
            const detailPack =
              detailState?.status === "success" ? detailState.pack : undefined;
            return (
              <section
                aria-labelledby={`pack-${pack.id}`}
                className="rounded-xl border border-line bg-surface p-4 shadow-sm sm:p-5"
                key={pack.id}
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h2
                      className="text-lg font-black text-foreground"
                      id={`pack-${pack.id}`}
                    >
                      Pack from {formatDateTime(pack.createdAt)}
                    </h2>
                    <p className="mt-1 text-xs text-muted">
                      Job version {pack.jobVersion} · Resume version{" "}
                      {pack.resumeVersionNumber} · Application version{" "}
                      {pack.applicationVersion}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Badge
                        tone={
                          pack.status === "generated" ? "success" : "danger"
                        }
                      >
                        {humanize(pack.status)}
                      </Badge>
                      <Badge tone={consistencyTone(status)}>
                        Consistency: {humanize(status)}
                      </Badge>
                    </div>
                  </div>
                  <Button
                    className="min-h-9 px-3"
                    loading={busyKey === `pack-${pack.id}`}
                    onClick={() => void refreshPack(pack.id)}
                    variant="secondary"
                  >
                    <RefreshCcw aria-hidden="true" className="size-4" />
                    Refresh checks
                  </Button>
                </div>

                {findings.length ? (
                  <Alert
                    className="mt-4"
                    title="Consistency findings"
                    tone={status === "failed" ? "danger" : "warning"}
                  >
                    <ul className="list-disc space-y-1 pl-4">
                      {findings.map((finding, index) => (
                        <li key={`${finding.code}-${index}`}>
                          <span className="font-bold">
                            {humanize(finding.severity)}:
                          </span>{" "}
                          {finding.message}
                        </li>
                      ))}
                    </ul>
                  </Alert>
                ) : (
                  <Alert
                    className="mt-4"
                    title="Consistency check passed"
                    tone="success"
                  >
                    No conflicting or unsupported application claims were
                    reported for this pack.
                  </Alert>
                )}

                <details
                  className="mt-5 rounded-xl border border-line"
                  onToggle={(event) => {
                    if (event.currentTarget.open && !detailState) {
                      void loadPackDetails(pack.id);
                    }
                  }}
                >
                  <summary className="min-h-12 cursor-pointer list-none px-3 py-3 text-sm font-black text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary-soft">
                    View generated documents
                  </summary>
                  <div className="border-t border-line p-3 sm:p-4">
                    {detailState?.status === "pending" && (
                      <p className="text-sm text-muted" role="status">
                        Loading generated documents...
                      </p>
                    )}
                    {detailState?.status === "error" && (
                      <Alert
                        title="Generated documents unavailable"
                        tone="danger"
                      >
                        <p>{detailState.message}</p>
                        <Button
                          className="mt-3 min-h-9 px-3"
                          onClick={() => void loadPackDetails(pack.id)}
                          variant="secondary"
                        >
                          Retry generated documents
                        </Button>
                      </Alert>
                    )}
                    {detailPack?.documents.length ? (
                      <ul className="space-y-3">
                        {detailPack.documents.map((document) => (
                          <li
                            className="rounded-xl border border-line"
                            key={document.id}
                          >
                            <details>
                              <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 p-3 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary-soft">
                                <span className="flex min-w-0 items-center gap-2">
                                  <FileCheck2
                                    aria-hidden="true"
                                    className="size-4 shrink-0 text-primary"
                                  />
                                  <span className="truncate text-sm font-black text-foreground">
                                    {document.title}
                                  </span>
                                </span>
                                <span className="flex shrink-0 gap-2">
                                  <Badge
                                    tone={
                                      document.status === "generated"
                                        ? "success"
                                        : "danger"
                                    }
                                  >
                                    {humanize(document.status)}
                                  </Badge>
                                  <Badge
                                    tone={consistencyTone(
                                      document.consistencyStatus,
                                    )}
                                  >
                                    {humanize(document.consistencyStatus)}
                                  </Badge>
                                </span>
                              </summary>
                              <div className="border-t border-line p-4">
                                {document.consistencyFindings.length > 0 && (
                                  <Alert
                                    className="mb-4"
                                    title="Document findings"
                                    tone={
                                      document.consistencyStatus === "failed"
                                        ? "danger"
                                        : "warning"
                                    }
                                  >
                                    <ul className="list-disc space-y-1 pl-4">
                                      {document.consistencyFindings.map(
                                        (finding, index) => (
                                          <li key={`${finding.code}-${index}`}>
                                            {finding.message}
                                          </li>
                                        ),
                                      )}
                                    </ul>
                                  </Alert>
                                )}
                                <div className="rounded-xl bg-surface-subtle p-4">
                                  <p className="whitespace-pre-wrap text-sm leading-6 text-foreground">
                                    {document.body ||
                                      "This document was blocked before content could be displayed."}
                                  </p>
                                </div>
                                <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                                  <div>
                                    <dt className="font-bold text-muted">
                                      Grounded claims
                                    </dt>
                                    <dd>{document.claims.length}</dd>
                                  </div>
                                  <div>
                                    <dt className="font-bold text-muted">
                                      Source evidence
                                    </dt>
                                    <dd>{document.sourceEvidenceIds.length}</dd>
                                  </div>
                                  <div>
                                    <dt className="font-bold text-muted">
                                      Supported requirements
                                    </dt>
                                    <dd>
                                      {document.sourceRequirementIds.length}
                                    </dd>
                                  </div>
                                  <div>
                                    <dt className="font-bold text-muted">
                                      Content fingerprint
                                    </dt>
                                    <dd className="truncate font-mono text-xs">
                                      {document.contentSha256}
                                    </dd>
                                  </div>
                                </dl>
                                {document.claims.length > 0 && (
                                  <div className="mt-4">
                                    <h3 className="text-sm font-black text-foreground">
                                      Claim provenance
                                    </h3>
                                    <ul className="mt-2 space-y-2">
                                      {document.claims.map((claim) => (
                                        <li
                                          className="rounded-lg border border-line p-3 text-sm"
                                          key={claim.id}
                                        >
                                          <p className="text-foreground">
                                            {claim.text}
                                          </p>
                                          <p className="mt-1 text-xs text-muted">
                                            {claim.evidenceLinks.length}{" "}
                                            evidence link
                                            {claim.evidenceLinks.length === 1
                                              ? ""
                                              : "s"}
                                            {" · "}
                                            {claim.requirementIds.length}{" "}
                                            supported requirement
                                            {claim.requirementIds.length === 1
                                              ? ""
                                              : "s"}
                                          </p>
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                                <Button
                                  className="mt-4"
                                  onClick={() =>
                                    setDeleteTarget({
                                      document,
                                      packId: pack.id,
                                    })
                                  }
                                  variant="danger"
                                >
                                  <Trash2
                                    aria-hidden="true"
                                    className="size-4"
                                  />
                                  Delete document
                                </Button>
                              </div>
                            </details>
                          </li>
                        ))}
                      </ul>
                    ) : detailPack ? (
                      <p className="text-sm text-muted">
                        This pack contains no displayable documents.
                      </p>
                    ) : null}
                  </div>
                </details>
              </section>
            );
          })}
        </div>
      ) : packs.status === "success" ? (
        <EmptyState
          description="Choose the document drafts above. Generation remains explicit and evidence-grounded."
          title="No application packs yet"
        />
      ) : null}
      {packs.hasMore && (
        <Button
          disabled={!packs.nextCursor}
          loading={packs.status === "pending"}
          onClick={() => void loadPacks(packs.nextCursor ?? undefined)}
          variant="secondary"
        >
          Load more application packs
        </Button>
      )}

      <ConfirmDialog
        confirmLabel="Delete document"
        description={
          <>
            Delete <strong>{deleteTarget?.document.title}</strong>? This removes
            the generated document from the application pack. The pinned resume
            and evidence records are not changed.
          </>
        }
        loading={
          Boolean(deleteTarget) &&
          busyKey === `delete-${deleteTarget?.document.id}`
        }
        onConfirm={() => void removeDocument()}
        onOpenChange={(open) => {
          if (!open && !busyKey?.startsWith("delete-")) {
            setDeleteTarget(undefined);
          }
        }}
        open={Boolean(deleteTarget)}
        title="Delete generated document?"
      />
    </div>
  );
}
