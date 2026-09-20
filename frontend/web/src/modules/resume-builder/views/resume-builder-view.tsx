"use client";

import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Download,
  FileText,
  History,
  Plus,
  RotateCcw,
  Save,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";

import {
  Alert,
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Input,
  LoadingSkeleton,
  Select,
  SectionHeader,
  cn,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import { loadResumeBuilderReadiness } from "../api/readiness-api";
import {
  createDownloadIntent,
  createResume,
  createVersion,
  exportVersion,
  listResumes,
  listVersions,
  restoreVersion,
  updateResume,
  waitForExportCompletion,
} from "../api/resume-builder-api";
import type {
  Resume,
  ResumeExportRecord,
  ResumeSectionResponse,
  ResumeVersion,
} from "../api/types";
import {
  ResumeBuilderReadinessPanel,
  ResumeSourcePreview,
} from "../components/resume-builder-readiness-panel";
import type { ResumeBuilderReadinessSnapshot } from "../lib/readiness";

const templates = [
  ["standard_professional", "Standard Professional"],
  ["compact_technical", "Compact Technical"],
  ["executive", "Executive"],
  ["graduate", "Graduate"],
  ["consulting_finance", "Consulting and Finance"],
] as const;

const formats = [
  ["pdf", "PDF"],
  ["docx", "DOCX"],
  ["text", "Text"],
  ["json", "JSON"],
] as const;

type TemplateValue = (typeof templates)[number][0];
type FormatValue = (typeof formats)[number][0];

const INITIAL_READINESS: ResumeBuilderReadinessSnapshot = {
  confirmedEvidenceCount: 0,
  draftEvidenceCount: 0,
  experienceCount: 0,
  skillCount: 0,
  status: "loading",
  steps: [],
};

export function ResumeBuilderView() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [versions, setVersions] = useState<ResumeVersion[]>([]);
  const [exportRecord, setExportRecord] = useState<ResumeExportRecord>();
  const [downloadUrl, setDownloadUrl] = useState<string>();
  const [loadError, setLoadError] = useState<string>();
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [readiness, setReadiness] =
    useState<ResumeBuilderReadinessSnapshot>(INITIAL_READINESS);
  const [busyKey, setBusyKey] = useState("initial");
  const [title, setTitle] = useState("Focused Resume");
  const [targetRole, setTargetRole] = useState("");
  const [template, setTemplate] = useState<TemplateValue>(
    "standard_professional",
  );
  const [format, setFormat] = useState<FormatValue>("pdf");
  const exportController = useRef<AbortController | undefined>(undefined);
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;

  const selected = useMemo(
    () => resumes.find((item) => item.id === selectedId),
    [resumes, selectedId],
  );

  const applyListedResumes = useCallback((items: Resume[]) => {
    setResumes(items);
    const first = items[0];
    if (first) {
      setSelectedId(first.id);
      setTitle(first.title);
      setTargetRole(first.targetRole ?? "");
      setTemplate(first.template);
    } else {
      setSelectedId("");
    }
  }, []);

  const refreshReadiness = useCallback(async () => {
    const snapshot = await loadResumeBuilderReadiness({ cacheBust: true });
    setReadiness(snapshot);
    return snapshot;
  }, []);

  const refreshWorkspace = useCallback(async () => {
    const [items, snapshot] = await Promise.all([
      listResumes(),
      loadResumeBuilderReadiness({ cacheBust: true }),
    ]);
    setReadiness(snapshot);
    setResumes(items);

    const preserved =
      items.find((item) => item.id === selectedIdRef.current) ?? items[0];
    if (preserved) {
      setSelectedId(preserved.id);
      setTitle(preserved.title);
      setTargetRole(preserved.targetRole ?? "");
      setTemplate(preserved.template);
      try {
        setVersions(await listVersions(preserved.id));
      } catch {
        setVersions([]);
      }
    } else {
      setSelectedId("");
      setVersions([]);
    }
    return snapshot;
  }, []);

  const load = useCallback(async () => {
    setBusyKey("initial");
    setLoadError(undefined);
    setFailure(undefined);
    try {
      const [items] = await Promise.all([
        listResumes(),
        refreshReadiness(),
      ]);
      applyListedResumes(items);
    } catch (error) {
      setLoadError(
        requestErrorMessage(error, "Resume Builder could not load."),
      );
    } finally {
      setBusyKey("");
    }
  }, [applyListedResumes, refreshReadiness]);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  useEffect(
    () => () => {
      exportController.current?.abort();
    },
    [],
  );

  useEffect(() => {
    if (!selected) return;
    const resumeId = selected.id;
    let active = true;
    async function loadVersions() {
      try {
        const items = await listVersions(resumeId);
        if (active) setVersions(items);
      } catch {
        if (active) setVersions([]);
      }
    }
    void loadVersions();
    return () => {
      active = false;
    };
  }, [selected]);

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (readiness.status !== "ready") return;
    await run("create", async () => {
      const created = await createResume({
        targetRole: targetRole.trim() || null,
        template,
        title: title.trim(),
      });
      setResumes((items) => [created, ...items]);
      setSelectedId(created.id);
      setVersions([]);
      setExportRecord(undefined);
      setDownloadUrl(undefined);
      setSuccess("Resume created from eligible confirmed evidence.");
      await refreshReadiness();
    });
  }

  async function saveDraft() {
    if (!selected) return;
    await run("save", async () => {
      const updated = await updateResume(selected, {
        targetRole: targetRole.trim() || null,
        template,
        title: title.trim(),
      });
      replaceResume(updated);
      setSuccess("Resume saved.");
    });
  }

  async function moveSection(index: number, direction: -1 | 1) {
    if (!selected) return;
    const sections = [...selected.currentVersion.sections];
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= sections.length) return;
    const [section] = sections.splice(index, 1);
    if (!section) return;
    sections.splice(nextIndex, 0, section);
    await run(`move-${section.id}`, async () => {
      const updated = await updateResume(selected, { sections });
      replaceResume(updated);
      setSuccess("Section order saved.");
    });
  }

  async function addGroundedBullet(section: ResumeSectionResponse) {
    if (!selected) return;
    const source = selected.currentVersion.sections
      .flatMap((value) => value.items)
      .find((item) => item.evidenceIds.length > 0);
    if (!source) return;
    const sections = selected.currentVersion.sections.map((value) =>
      value.id === section.id
        ? {
            ...value,
            items: [
              ...value.items,
              {
                ...source,
                id: crypto.randomUUID(),
                source: source.source || "career_record",
              },
            ],
          }
        : value,
    );
    await run(`add-${section.id}`, async () => {
      const updated = await updateResume(selected, { sections });
      replaceResume(updated);
      setSuccess("Grounded bullet added.");
    });
  }

  async function snapshotVersion() {
    if (!selected) return;
    await run("version", async () => {
      const version = await createVersion(selected);
      setVersions((items) => [...items, version]);
      setSuccess(`Version ${version.versionNumber} saved.`);
    });
  }

  async function restore(versionId: string) {
    if (!selected) return;
    await run(`restore-${versionId}`, async () => {
      const restored = await restoreVersion(selected, versionId);
      replaceResume(restored);
      setTitle(restored.title);
      setTargetRole(restored.targetRole ?? "");
      setTemplate(restored.template);
      setSuccess("Version restored.");
    });
  }

  async function exportCurrent() {
    if (!selected) return;
    exportController.current?.abort();
    const controller = new AbortController();
    exportController.current = controller;
    await run("export", async () => {
      const pendingRecord = await exportVersion(selected.currentVersion.id, {
        format,
      });
      setExportRecord(pendingRecord);
      setDownloadUrl(undefined);
      const record = await waitForExportCompletion(
        pendingRecord,
        controller.signal,
      );
      setExportRecord(record);
      if (record.export.status === "blocked") {
        setFailure("Round-trip verification blocked this export.");
      } else if (record.export.status !== "verified") {
        setFailure("The export could not be verified.");
      } else {
        setSuccess("Export verified.");
      }
    });
    if (exportController.current === controller) {
      exportController.current = undefined;
    }
  }

  async function downloadExport() {
    if (!exportRecord) return;
    await run("download", async () => {
      const intent = await createDownloadIntent(exportRecord.export.id);
      setDownloadUrl(intent.url);
      setSuccess("Download is ready.");
    });
  }

  async function run(key: string, action: () => Promise<void>) {
    setBusyKey(key);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      await action();
    } catch (error) {
      setFailure(
        requestErrorMessage(
          error,
          "Resume Builder could not complete that action.",
        ),
      );
    } finally {
      setBusyKey("");
    }
  }

  async function handleRefreshReadiness() {
    setBusyKey("readiness");
    setFailure(undefined);
    setSuccess(undefined);
    setExportRecord(undefined);
    setDownloadUrl(undefined);
    try {
      await refreshWorkspace();
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "Resume readiness could not refresh."),
      );
    } finally {
      setBusyKey("");
    }
  }

  function replaceResume(next: Resume) {
    setResumes((items) =>
      items.map((item) => (item.id === next.id ? next : item)),
    );
  }

  if (busyKey === "initial") return <ResumeBuilderLoading />;
  if (loadError && resumes.length === 0) {
    return (
      <section className="space-y-6" id="resume-builder">
        <ErrorState
          description={loadError}
          onRetry={() => void load()}
          title="Resume Builder could not load"
        />
      </section>
    );
  }

  const createBlocked = readiness.status !== "ready";
  const sourceOptions = readiness.sourceOptions;
  const nextIncompleteStep = readiness.steps.find((step) => !step.complete);

  return (
    <section className="space-y-6" id="resume-builder">
      <div aria-live="polite" className="sr-only">
        {success || failure || ""}
      </div>

      <SectionHeader
        description="Create evidence-backed resume versions, inspect exactly what each version contains, and verify the final file before downloading it."
        id="resume-builder-heading"
        title="Resume Builder"
      />

      <section
        aria-labelledby="create-resume-heading"
        className="rounded-card border border-border bg-surface-raised p-4 sm:p-5"
      >
        <SectionHeader
          description="A resume starts from confirmed evidence in Evidence Vault. Creating one does not publish or export it."
          id="create-resume-heading"
          title="Create a resume"
        />

        <ResumeBuilderReadinessPanel
          onRefresh={() => void handleRefreshReadiness()}
          readiness={readiness}
          refreshing={busyKey === "readiness"}
        />

        {readiness.status === "ready" && sourceOptions && (
          <ResumeSourcePreview
            bulletCount={sourceOptions.bullets.length}
            headline={sourceOptions.headline}
            skillCount={sourceOptions.skills.length}
            sourceEvidenceCount={sourceOptions.sourceEvidenceIds.length}
          />
        )}

        {createBlocked && nextIncompleteStep && (
          <Alert
            className="mt-4"
            id="resume-source-required"
            title="Resume source not ready"
            tone="info"
          >
            Complete the checklist above before creating a resume. Resume Builder
            will not invent facts to fill a blank draft.
          </Alert>
        )}

        {failure && (
          <Alert className="mt-4" title="Action failed" tone="danger">
            {failure}
          </Alert>
        )}
        {success && (
          <Alert className="mt-4" title="Ready" tone="success">
            {success}
          </Alert>
        )}
        <form
          aria-describedby={
            createBlocked ? "resume-source-required" : undefined
          }
          aria-label="Create a resume"
          className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-[minmax(0,12rem)_minmax(0,13rem)_12rem_auto]"
          onSubmit={(event) => void submitCreate(event)}
        >
          <label className="sr-only" htmlFor="resume-title">
            Resume title
          </label>
          <Input
            id="resume-title"
            maxLength={120}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Resume title"
            required
            value={title}
          />
          <label className="sr-only" htmlFor="target-role">
            Target role
          </label>
          <Input
            id="target-role"
            maxLength={120}
            onChange={(event) => setTargetRole(event.target.value)}
            placeholder="Target role"
            value={targetRole}
          />
          <label className="sr-only" htmlFor="template">
            Template
          </label>
          <Select
            id="template"
            onChange={(event) =>
              setTemplate(event.target.value as TemplateValue)
            }
            value={template}
          >
            {templates.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
          <Button
            disabled={createBlocked}
            loading={busyKey === "create"}
            type="submit"
          >
            <FileText aria-hidden="true" className="size-4" />
            Create
          </Button>
        </form>
      </section>

      {resumes.length === 0 ? (
        readiness.status === "ready" ? (
          <EmptyState
            description="Your evidence is ready. Use the form above to create your first grounded resume draft."
            title="No resumes yet"
          />
        ) : null
      ) : (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <section aria-labelledby="editor-heading" className="space-y-4">
            <div className="rounded-card border border-border bg-surface-raised p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <h2
                    className="text-lg font-black text-foreground"
                    id="editor-heading"
                  >
                    Current working version
                  </h2>
                  {selected && (
                    <p className="mt-1 text-sm text-muted">
                      Version {selected.currentVersion.versionNumber} · Changes
                      remain in this version until you create a new snapshot.
                    </p>
                  )}
                </div>
                <div className="grid gap-2 sm:grid-cols-[minmax(0,13rem)_auto_auto]">
                  <label className="sr-only" htmlFor="resume-select">
                    Resume
                  </label>
                  <Select
                    id="resume-select"
                    onChange={(event) => {
                      const next = resumes.find(
                        (item) => item.id === event.target.value,
                      );
                      setSelectedId(event.target.value);
                      setVersions([]);
                      setExportRecord(undefined);
                      setDownloadUrl(undefined);
                      if (next) {
                        setTitle(next.title);
                        setTargetRole(next.targetRole ?? "");
                        setTemplate(next.template);
                      }
                    }}
                    value={selectedId}
                  >
                    {resumes.map((resume) => (
                      <option key={resume.id} value={resume.id}>
                        {resume.title}
                      </option>
                    ))}
                  </Select>
                  <Button
                    disabled={!selected}
                    loading={busyKey === "save"}
                    onClick={() => void saveDraft()}
                    type="button"
                    variant="secondary"
                  >
                    <Save aria-hidden="true" className="size-4" />
                    Save changes
                  </Button>
                  <Button
                    disabled={!selected}
                    loading={busyKey === "version"}
                    onClick={() => void snapshotVersion()}
                    type="button"
                  >
                    <History aria-hidden="true" className="size-4" />
                    Create version
                  </Button>
                </div>
              </div>
            </div>

            {selected && (
              <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <section
                  aria-label="Resume sections"
                  className="rounded-card border border-border bg-surface-raised p-4"
                >
                  <div className="space-y-3">
                    {selected.currentVersion.sections.map((section, index) => (
                      <article
                        className="rounded-control border border-border bg-surface-subtle p-3"
                        key={section.id}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <h3 className="text-sm font-black text-foreground">
                              {section.title}
                            </h3>
                            <p className="text-xs text-muted">{section.kind}</p>
                          </div>
                          <div className="flex gap-1">
                            <IconButton
                              disabled={index === 0}
                              label={`Move ${section.title} up`}
                              loading={busyKey === `move-${section.id}`}
                              onClick={() => void moveSection(index, -1)}
                            >
                              <ArrowUp aria-hidden="true" className="size-4" />
                            </IconButton>
                            <IconButton
                              disabled={
                                index ===
                                selected.currentVersion.sections.length - 1
                              }
                              label={`Move ${section.title} down`}
                              loading={busyKey === `move-${section.id}`}
                              onClick={() => void moveSection(index, 1)}
                            >
                              <ArrowDown
                                aria-hidden="true"
                                className="size-4"
                              />
                            </IconButton>
                            <IconButton
                              label={`Add grounded bullet to ${section.title}`}
                              loading={busyKey === `add-${section.id}`}
                              onClick={() => void addGroundedBullet(section)}
                            >
                              <Plus aria-hidden="true" className="size-4" />
                            </IconButton>
                          </div>
                        </div>
                        <ul className="mt-3 space-y-2">
                          {section.items.length === 0 ? (
                            <li className="text-sm text-muted">No items</li>
                          ) : (
                            section.items.map((item) => (
                              <li
                                className="text-sm text-foreground"
                                key={item.id}
                              >
                                {item.text}
                                <span className="ml-2 text-xs text-muted">
                                  {item.evidenceIds.length} evidence source
                                  {item.evidenceIds.length === 1 ? "" : "s"}
                                </span>
                              </li>
                            ))
                          )}
                        </ul>
                      </article>
                    ))}
                  </div>
                </section>

                <section
                  aria-label="Plain text preview"
                  className="rounded-card border border-border bg-surface-raised p-4"
                >
                  <h2 className="text-sm font-black text-foreground">
                    Recruiter preview
                  </h2>
                  <pre className="mt-3 max-h-[34rem] overflow-auto whitespace-pre-wrap rounded-control bg-navy p-4 text-sm leading-6 text-white">
                    {selected.currentVersion.plainText}
                  </pre>
                </section>
              </div>
            )}
          </section>

          <aside className="space-y-4">
            <section
              aria-labelledby="export-heading"
              className="rounded-card border border-border bg-surface-raised p-4"
            >
              <h2
                className="text-lg font-black text-foreground"
                id="export-heading"
              >
                Verify and export
              </h2>
              <p className="mt-1 text-sm leading-6 text-muted">
                Verification checks the selected version and format. The source
                version remains immutable after export.
              </p>
              <div className="mt-4 grid gap-2 sm:grid-cols-[1fr_auto] xl:grid-cols-1">
                <label className="sr-only" htmlFor="export-format">
                  Export format
                </label>
                <Select
                  id="export-format"
                  onChange={(event) =>
                    setFormat(event.target.value as FormatValue)
                  }
                  value={format}
                >
                  {formats.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </Select>
                <Button
                  disabled={!selected}
                  loading={busyKey === "export"}
                  onClick={() => void exportCurrent()}
                  type="button"
                >
                  <CheckCircle2 aria-hidden="true" className="size-4" />
                  Verify
                </Button>
              </div>

              {exportRecord && (
                <div className="mt-4 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <Badge
                      tone={
                        exportRecord.export.status === "blocked"
                          ? "danger"
                          : exportRecord.export.verificationStatus === "warning"
                            ? "warning"
                            : "success"
                      }
                    >
                      {exportRecord.export.status}
                    </Badge>
                    <span className="text-xs text-muted">
                      {exportRecord.export.sizeBytes} bytes
                    </span>
                  </div>
                  {["pending", "rendering", "retry_wait"].includes(
                    exportRecord.export.status,
                  ) ? (
                    <Alert title="Verification in progress" tone="info">
                      The durable export worker is rendering and checking this
                      file.
                    </Alert>
                  ) : exportRecord.verification?.criticalFailures.length ? (
                    <Alert title="Blocked" tone="danger">
                      {exportRecord.verification.criticalFailures.join(", ")}
                    </Alert>
                  ) : exportRecord.verification?.warnings.length ? (
                    <Alert title="Warnings" tone="warning">
                      {exportRecord.verification.warnings.join(", ")}
                    </Alert>
                  ) : exportRecord.export.status === "verified" ? (
                    <Alert title="Round-trip verified" tone="success">
                      Searchable output matched the source version.
                    </Alert>
                  ) : (
                    <Alert title="Export unavailable" tone="danger">
                      This export did not pass durable verification. Try again
                      or review the recorded failure.
                    </Alert>
                  )}
                  <Button
                    disabled={exportRecord.export.status !== "verified"}
                    loading={busyKey === "download"}
                    onClick={() => void downloadExport()}
                    type="button"
                    variant="secondary"
                  >
                    <Download aria-hidden="true" className="size-4" />
                    Download
                  </Button>
                  {downloadUrl && (
                    <a
                      className="block break-all text-sm font-semibold text-primary underline-offset-4 hover:underline"
                      href={downloadUrl}
                      rel="noreferrer"
                    >
                      {downloadUrl}
                    </a>
                  )}
                </div>
              )}
            </section>

            <section
              aria-labelledby="history-heading"
              className="rounded-card border border-border bg-surface-raised p-4"
            >
              <h2
                className="text-lg font-black text-foreground"
                id="history-heading"
              >
                Version history
              </h2>
              <div className="mt-4 space-y-2">
                {versions.length === 0 ? (
                  <p className="text-sm text-muted">
                    No saved version history yet.
                  </p>
                ) : (
                  versions.map((version) => (
                    <div
                      className={cn(
                        "flex items-center justify-between gap-3 rounded-control border border-border p-3",
                        selected?.currentVersionId === version.id &&
                          "bg-primary-soft",
                      )}
                      key={version.id}
                    >
                      <div>
                        <p className="text-sm font-bold text-foreground">
                          Version {version.versionNumber}
                        </p>
                        <p className="text-xs text-muted">{version.title}</p>
                      </div>
                      <IconButton
                        disabled={selected?.currentVersionId === version.id}
                        label={`Restore version ${version.versionNumber}`}
                        loading={busyKey === `restore-${version.id}`}
                        onClick={() => void restore(version.id)}
                      >
                        <RotateCcw aria-hidden="true" className="size-4" />
                      </IconButton>
                    </div>
                  ))
                )}
              </div>
            </section>
          </aside>
        </div>
      )}
    </section>
  );
}

function IconButton({
  children,
  disabled,
  label,
  loading,
  onClick,
}: {
  children: ReactNode;
  disabled?: boolean;
  label: string;
  loading?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      aria-label={label}
      className="grid size-9 place-items-center rounded-control border border-border bg-surface-raised text-muted transition hover:border-primary hover:text-primary focus:outline-none focus:ring-3 focus:ring-primary-soft disabled:cursor-not-allowed disabled:opacity-50"
      disabled={disabled || loading}
      onClick={onClick}
      title={label}
      type="button"
    >
      {loading ? (
        <AlertTriangle aria-hidden="true" className="size-4" />
      ) : (
        children
      )}
    </button>
  );
}

function ResumeBuilderLoading() {
  return (
    <div className="space-y-6">
      <LoadingSkeleton variant="page" />
    </div>
  );
}
