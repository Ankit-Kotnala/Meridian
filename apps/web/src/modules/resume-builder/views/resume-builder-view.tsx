"use client";

import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Columns3,
  Download,
  Eye,
  FileText,
  History,
  Plus,
  Redo2,
  RotateCcw,
  Save,
  Trash2,
  Undo2,
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
  cn,
} from "@careeros/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  createDownloadIntent,
  createResume,
  createVersion,
  deleteExport,
  exportVersion,
  getExport,
  getResumeSourceOptions,
  listResumes,
  listVersions,
  restoreVersion,
  updateResume,
} from "../api/resume-builder-api";
import type {
  Resume,
  ResumeExportRecord,
  ResumeSourceOptions,
  ResumeVersion,
} from "../api/types";
import {
  changedLines,
  cloneDraft,
  draftFromResume,
  draftPlainText,
  draftUpdateInput,
  sameDraft,
  type DraftSection,
  type ResumeDraft,
} from "./editor-state";

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

const terminalExportStatuses = new Set([
  "verified",
  "blocked",
  "failed",
  "dead_lettered",
  "deletion_dead_lettered",
  "deleted",
]);
const terminalDeletionStatuses = new Set(["deleted", "deletion_dead_lettered"]);

type TemplateValue = (typeof templates)[number][0];
type FormatValue = (typeof formats)[number][0];
type PreviewMode = "page" | "plain" | "recruiter";
type SaveStatus = "idle" | "unsaved" | "saving" | "saved" | "conflict";

export function ResumeBuilderView() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [versions, setVersions] = useState<ResumeVersion[]>([]);
  const [sourceOptions, setSourceOptions] = useState<ResumeSourceOptions>();
  const [draft, setDraft] = useState<ResumeDraft>();
  const [undoStack, setUndoStack] = useState<ResumeDraft[]>([]);
  const [redoStack, setRedoStack] = useState<ResumeDraft[]>([]);
  const [dirty, setDirty] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [sourceChoice, setSourceChoice] = useState<Record<string, string>>({});
  const [compareVersionId, setCompareVersionId] = useState("");
  const [previewMode, setPreviewMode] = useState<PreviewMode>("page");
  const [exportRecord, setExportRecord] = useState<ResumeExportRecord>();
  const [downloadUrl, setDownloadUrl] = useState<string>();
  const [failure, setFailure] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [busyKey, setBusyKey] = useState("initial");
  const [newTitle, setNewTitle] = useState("Focused Resume");
  const [newTargetRole, setNewTargetRole] = useState("");
  const [newTemplate, setNewTemplate] = useState<TemplateValue>(
    "standard_professional",
  );
  const [format, setFormat] = useState<FormatValue>("pdf");
  const [autosaveEpoch, setAutosaveEpoch] = useState(0);
  const draftRevision = useRef(0);
  const saveInFlight = useRef(false);
  const selectedIdRef = useRef("");

  const selected = useMemo(
    () => resumes.find((item) => item.id === selectedId),
    [resumes, selectedId],
  );
  const comparison = useMemo(
    () => versions.find((version) => version.id === compareVersionId),
    [compareVersionId, versions],
  );
  const acceptPersistedResume = useCallback(
    (updated: Resume, resumeId: string, revision: number): boolean => {
      replaceResumeState(setResumes, updated);
      if (selectedIdRef.current !== resumeId) return false;
      setVersions((items) => appendVersion(items, updated.currentVersion));
      if (draftRevision.current !== revision) {
        setSaveStatus("unsaved");
        return false;
      }
      setDraft(draftFromResume(updated));
      setDirty(false);
      setSaveStatus("saved");
      return true;
    },
    [],
  );

  useEffect(() => {
    let active = true;
    async function load() {
      setBusyKey("initial");
      setFailure(undefined);
      try {
        const items = await listResumes();
        if (!active) return;
        setResumes(items);
        const first = items[0];
        if (first) {
          selectedIdRef.current = first.id;
          setSelectedId(first.id);
          setDraft(draftFromResume(first));
        }
      } catch (error) {
        if (active) {
          setFailure(
            requestErrorMessage(error, "Resume Builder could not load."),
          );
        }
      } finally {
        if (active) setBusyKey("");
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    const resumeId = selectedId;
    let active = true;
    async function loadRelatedData() {
      try {
        const [versionItems, options] = await Promise.all([
          listVersions(resumeId),
          getResumeSourceOptions(resumeId),
        ]);
        if (!active) return;
        setVersions(versionItems);
        setSourceOptions(options);
      } catch (error) {
        if (active) {
          setFailure(
            requestErrorMessage(
              error,
              "Eligible source facts or version history could not be loaded.",
            ),
          );
        }
      }
    }
    void loadRelatedData();
    return () => {
      active = false;
    };
  }, [selectedId]);

  useEffect(() => {
    if (
      !dirty ||
      !draft ||
      !selected ||
      saveStatus === "conflict" ||
      saveInFlight.current
    ) {
      return;
    }
    const resume = selected;
    const revision = draftRevision.current;
    const resumeId = resume.id;
    const timeout = window.setTimeout(async () => {
      if (saveInFlight.current) {
        setAutosaveEpoch((value) => value + 1);
        return;
      }
      saveInFlight.current = true;
      setSaveStatus("saving");
      try {
        const updated = await updateResume(resume, draftUpdateInput(draft));
        acceptPersistedResume(updated, resumeId, revision);
      } catch (error) {
        if (selectedIdRef.current === resumeId) {
          setSaveStatus("conflict");
          setFailure(
            requestErrorMessage(
              error,
              "Autosave could not apply. Your local draft is preserved; reload or restore after reviewing the conflict.",
            ),
          );
        }
      } finally {
        saveInFlight.current = false;
        setAutosaveEpoch((value) => value + 1);
      }
    }, 800);
    return () => window.clearTimeout(timeout);
  }, [
    acceptPersistedResume,
    autosaveEpoch,
    dirty,
    draft,
    saveStatus,
    selected,
  ]);

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run("create", async () => {
      const created = await createResume({
        targetRole: newTargetRole.trim() || null,
        template: newTemplate,
        title: newTitle.trim(),
      });
      setResumes((items) => [created, ...items]);
      selectedIdRef.current = created.id;
      draftRevision.current += 1;
      setSelectedId(created.id);
      setDraft(draftFromResume(created));
      setUndoStack([]);
      setRedoStack([]);
      setDirty(false);
      setSaveStatus("idle");
      setSuccess("Resume created from eligible Career Record evidence.");
    });
  }

  function changeDraft(transform: (current: ResumeDraft) => ResumeDraft) {
    setDraft((current) => {
      if (!current) return current;
      const next = transform(cloneDraft(current));
      if (sameDraft(current, next)) return current;
      draftRevision.current += 1;
      setUndoStack((items) => [...items.slice(-49), cloneDraft(current)]);
      setRedoStack([]);
      setDirty(true);
      setSaveStatus("unsaved");
      return next;
    });
  }

  function undo() {
    const previous = undoStack.at(-1);
    if (!previous || !draft) return;
    setUndoStack((items) => items.slice(0, -1));
    setRedoStack((items) => [...items.slice(-49), cloneDraft(draft)]);
    draftRevision.current += 1;
    setDraft(cloneDraft(previous));
    setDirty(true);
    setSaveStatus("unsaved");
  }

  function redo() {
    const next = redoStack.at(-1);
    if (!next || !draft) return;
    setRedoStack((items) => items.slice(0, -1));
    setUndoStack((items) => [...items.slice(-49), cloneDraft(draft)]);
    draftRevision.current += 1;
    setDraft(cloneDraft(next));
    setDirty(true);
    setSaveStatus("unsaved");
  }

  function selectResume(resumeId: string) {
    const resume = resumes.find((item) => item.id === resumeId);
    selectedIdRef.current = resumeId;
    draftRevision.current += 1;
    setSelectedId(resumeId);
    setDraft(resume ? draftFromResume(resume) : undefined);
    setUndoStack([]);
    setRedoStack([]);
    setDirty(false);
    setSaveStatus("idle");
    setExportRecord(undefined);
    setDownloadUrl(undefined);
    setSourceOptions(undefined);
  }

  async function saveDraft() {
    if (!selected || !draft || saveInFlight.current) return;
    const revision = draftRevision.current;
    saveInFlight.current = true;
    try {
      await run("save", async () => {
        setSaveStatus("saving");
        const updated = await updateResume(selected, draftUpdateInput(draft));
        if (acceptPersistedResume(updated, selected.id, revision)) {
          setSuccess("Resume saved.");
        }
      });
    } finally {
      saveInFlight.current = false;
      setAutosaveEpoch((value) => value + 1);
    }
  }

  function moveSection(index: number, direction: -1 | 1) {
    changeDraft((current) => {
      const nextIndex = index + direction;
      if (nextIndex < 0 || nextIndex >= current.sections.length) return current;
      const [section] = current.sections.splice(index, 1);
      if (section) current.sections.splice(nextIndex, 0, section);
      return current;
    });
  }

  function addSection() {
    changeDraft((current) => ({
      ...current,
      sections: [
        ...current.sections,
        {
          id: crypto.randomUUID(),
          items: [],
          kind: "custom",
          title: "New section",
        },
      ],
    }));
  }

  function updateSection(
    sectionId: string,
    patch: Partial<Pick<DraftSection, "kind" | "title">>,
  ) {
    changeDraft((current) => ({
      ...current,
      sections: current.sections.map((section) =>
        section.id === sectionId ? { ...section, ...patch } : section,
      ),
    }));
  }

  function removeSection(sectionId: string) {
    changeDraft((current) => {
      if (current.sections.length <= 1) return current;
      return {
        ...current,
        sections: current.sections.filter(
          (section) => section.id !== sectionId,
        ),
      };
    });
  }

  function addGroundedBullet(sectionId: string) {
    if (!sourceOptions) return;
    const choice = Number(sourceChoice[sectionId] ?? "0");
    const source = sourceOptions.bullets[choice];
    if (!source) return;
    changeDraft((current) => ({
      ...current,
      sections: current.sections.map((section) =>
        section.id === sectionId
          ? {
              ...section,
              items: [
                ...section.items,
                {
                  entityId: source.entityId,
                  evidenceIds: [...source.evidenceIds],
                  id: crypto.randomUUID(),
                  source: source.source,
                  text: source.text,
                },
              ],
            }
          : section,
      ),
    }));
  }

  function replaceGroundedBullet(
    sectionId: string,
    bulletId: string,
    sourceIndex: number,
  ) {
    const source = sourceOptions?.bullets[sourceIndex];
    if (!source) return;
    changeDraft((current) => ({
      ...current,
      sections: current.sections.map((section) =>
        section.id === sectionId
          ? {
              ...section,
              items: section.items.map((item) =>
                item.id === bulletId
                  ? {
                      entityId: source.entityId,
                      evidenceIds: [...source.evidenceIds],
                      id: item.id,
                      source: source.source,
                      text: source.text,
                    }
                  : item,
              ),
            }
          : section,
      ),
    }));
  }

  function removeBullet(sectionId: string, bulletId: string) {
    changeDraft((current) => ({
      ...current,
      sections: current.sections.map((section) =>
        section.id === sectionId
          ? {
              ...section,
              items: section.items.filter((item) => item.id !== bulletId),
            }
          : section,
      ),
    }));
  }

  function moveBullet(sectionId: string, index: number, direction: -1 | 1) {
    changeDraft((current) => ({
      ...current,
      sections: current.sections.map((section) => {
        if (section.id !== sectionId) return section;
        const nextIndex = index + direction;
        if (nextIndex < 0 || nextIndex >= section.items.length) return section;
        const items = [...section.items];
        const [item] = items.splice(index, 1);
        if (item) items.splice(nextIndex, 0, item);
        return { ...section, items };
      }),
    }));
  }

  async function snapshotVersion() {
    if (!selected || !draft || saveInFlight.current) return;
    const resume = selected;
    await run("version", async () => {
      let current = resume;
      if (dirty) {
        const revision = draftRevision.current;
        saveInFlight.current = true;
        try {
          current = await updateResume(resume, draftUpdateInput(draft));
          acceptPersistedResume(current, resume.id, revision);
        } finally {
          saveInFlight.current = false;
          setAutosaveEpoch((value) => value + 1);
        }
      }
      const version = await createVersion(current);
      if (selectedIdRef.current !== resume.id) return;
      setVersions((items) => appendVersion(items, version));
      setSuccess(`Version ${version.versionNumber} saved.`);
    });
  }

  async function restore(versionId: string) {
    if (!selected || saveInFlight.current) return;
    const resume = selected;
    draftRevision.current += 1;
    const revision = draftRevision.current;
    saveInFlight.current = true;
    setSaveStatus("saving");
    try {
      await run(`restore-${versionId}`, async () => {
        const restored = await restoreVersion(resume, versionId);
        const accepted = acceptPersistedResume(restored, resume.id, revision);
        if (accepted) {
          setUndoStack([]);
          setRedoStack([]);
          setCompareVersionId("");
          setSuccess("Version restored without changing immutable history.");
        } else if (selectedIdRef.current === resume.id) {
          setSuccess(
            "Version restored; newer local edits remain unsaved and will be applied next.",
          );
        }
      });
    } finally {
      saveInFlight.current = false;
      setAutosaveEpoch((value) => value + 1);
      if (
        selectedIdRef.current === resume.id &&
        draftRevision.current === revision
      ) {
        setSaveStatus((current) =>
          current === "saving" ? (dirty ? "unsaved" : "idle") : current,
        );
      }
    }
  }

  async function exportCurrent() {
    if (!selected) return;
    const resume = selected;
    await run("export", async () => {
      let record = await exportVersion(resume.currentVersion.id, { format });
      if (selectedIdRef.current !== resume.id) return;
      setExportRecord(record);
      setDownloadUrl(undefined);
      for (let attempt = 0; attempt < 60; attempt += 1) {
        if (terminalExportStatuses.has(record.export.status)) break;
        await delay(500);
        if (selectedIdRef.current !== resume.id) return;
        record = await getExport(record.export.id);
        if (selectedIdRef.current !== resume.id) return;
        setExportRecord(record);
      }
      if (selectedIdRef.current !== resume.id) return;
      if (record.export.status === "verified") {
        setSuccess("Export passed independent fidelity verification.");
      } else if (record.export.status === "blocked") {
        setFailure(
          "Fidelity verification blocked this export. No download was created.",
        );
      } else if (!terminalExportStatuses.has(record.export.status)) {
        setFailure(
          "Export is still processing. Its durable status remains available.",
        );
      } else {
        setFailure("Export processing ended without a downloadable artifact.");
      }
    });
  }

  async function downloadExport() {
    if (!exportRecord) return;
    const record = exportRecord;
    await run("download", async () => {
      const intent = await createDownloadIntent(record.export.id);
      if (selectedIdRef.current !== record.export.resumeId) return;
      setDownloadUrl(intent.url);
      setSuccess("Download is ready.");
    });
  }

  async function deleteCurrentExport() {
    if (!exportRecord) return;
    const selectedExport = exportRecord;
    await run("delete-export", async () => {
      let record = await deleteExport(selectedExport.export.id);
      if (selectedIdRef.current !== selectedExport.export.resumeId) return;
      setExportRecord(record);
      setDownloadUrl(undefined);
      for (let attempt = 0; attempt < 60; attempt += 1) {
        if (terminalDeletionStatuses.has(record.export.status)) break;
        await delay(500);
        if (selectedIdRef.current !== selectedExport.export.resumeId) return;
        record = await getExport(record.export.id);
        if (selectedIdRef.current !== selectedExport.export.resumeId) return;
        setExportRecord(record);
      }
      if (selectedIdRef.current !== selectedExport.export.resumeId) return;
      if (record.export.status === "deleted") {
        setSuccess(
          "Export file deleted. Immutable resume history is unchanged.",
        );
      } else if (record.export.status === "deletion_dead_lettered") {
        setFailure(
          "Export cleanup needs attention. The private object is retained and no download is available.",
        );
      } else {
        setFailure(
          "Export cleanup is still processing. Its durable status remains available.",
        );
      }
    });
  }

  async function run(key: string, action: () => Promise<void>) {
    setBusyKey(key);
    setFailure(undefined);
    setSuccess(undefined);
    try {
      await action();
    } catch (error) {
      if (key === "save") setSaveStatus("conflict");
      setFailure(
        requestErrorMessage(
          error,
          key === "save"
            ? "Save failed. Your local draft is preserved."
            : "Resume Builder could not complete that action.",
        ),
      );
    } finally {
      setBusyKey("");
    }
  }

  if (busyKey === "initial") return <ResumeBuilderLoading />;
  if (failure && resumes.length === 0) {
    return (
      <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" id="main-content">
        <ErrorState
          description={failure}
          title="Resume Builder could not load"
        />
      </main>
    );
  }

  return (
    <main
      className="mx-auto max-w-[96rem] space-y-6 p-4 sm:p-6 lg:p-8"
      id="main-content"
    >
      <div aria-live="polite" className="sr-only">
        {success || failure || saveStatusLabel(saveStatus)}
      </div>

      <header className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-primary">
            Resume Builder
          </p>
          <h1 className="mt-1 text-2xl font-black text-foreground">
            Evidence-backed resume studio
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Every factual line stays linked to confirmed Career Record or
            approved Change Studio evidence.
          </p>
        </div>
        <form
          aria-label="Create a resume"
          className="grid gap-2 sm:grid-cols-[minmax(0,12rem)_minmax(0,13rem)_11rem_auto]"
          onSubmit={(event) => void submitCreate(event)}
        >
          <Input
            aria-label="Resume title"
            maxLength={120}
            onChange={(event) => setNewTitle(event.target.value)}
            required
            value={newTitle}
          />
          <Input
            aria-label="Target role"
            maxLength={120}
            onChange={(event) => setNewTargetRole(event.target.value)}
            placeholder="Target role"
            value={newTargetRole}
          />
          <Select
            aria-label="Template"
            onChange={(event) =>
              setNewTemplate(event.target.value as TemplateValue)
            }
            value={newTemplate}
          >
            {templates.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
          <Button loading={busyKey === "create"} type="submit">
            <FileText aria-hidden="true" className="size-4" />
            Create
          </Button>
        </form>
      </header>

      {failure && resumes.length > 0 && (
        <Alert title="Action needs attention" tone="danger">
          {failure}
        </Alert>
      )}
      {success && (
        <Alert title="Ready" tone="success">
          {success}
        </Alert>
      )}

      {resumes.length === 0 ? (
        <EmptyState
          description="Add confirmed evidence in Career Profile before creating a resume."
          title="No resumes yet"
        />
      ) : (
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_27rem]">
          <section aria-labelledby="editor-heading" className="space-y-4">
            <EditorToolbar
              busyKey={busyKey}
              canRedo={redoStack.length > 0}
              canUndo={undoStack.length > 0}
              onRedo={redo}
              onSave={() => void saveDraft()}
              onSnapshot={() => void snapshotVersion()}
              onUndo={undo}
              resumes={resumes}
              saveStatus={saveStatus}
              selectedId={selectedId}
              setSelectedId={selectResume}
            />

            {selected && draft && (
              <>
                <ResumeFields
                  changeDraft={changeDraft}
                  draft={draft}
                  sourceOptions={sourceOptions}
                />
                <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(28rem,0.9fr)]">
                  <StructuredSections
                    addGroundedBullet={addGroundedBullet}
                    addSection={addSection}
                    changeDraft={changeDraft}
                    draft={draft}
                    moveBullet={moveBullet}
                    moveSection={moveSection}
                    removeBullet={removeBullet}
                    removeSection={removeSection}
                    replaceGroundedBullet={replaceGroundedBullet}
                    setSourceChoice={setSourceChoice}
                    sourceChoice={sourceChoice}
                    sourceOptions={sourceOptions}
                    updateSection={updateSection}
                  />
                  <Preview
                    draft={draft}
                    mode={previewMode}
                    setMode={setPreviewMode}
                    sourceOptions={sourceOptions}
                  />
                </div>
              </>
            )}
          </section>

          <aside className="space-y-4">
            <ExportPanel
              busyKey={busyKey}
              downloadUrl={downloadUrl}
              exportRecord={exportRecord}
              format={format}
              onDelete={() => void deleteCurrentExport()}
              onDownload={() => void downloadExport()}
              onExport={() => void exportCurrent()}
              setFormat={setFormat}
              selected={selected}
            />
            <HistoryPanel
              busyKey={busyKey}
              compareVersionId={compareVersionId}
              comparison={comparison}
              current={selected?.currentVersion}
              onRestore={(versionId) => void restore(versionId)}
              setCompareVersionId={setCompareVersionId}
              versions={versions}
            />
          </aside>
        </div>
      )}
    </main>
  );
}

function EditorToolbar({
  busyKey,
  canRedo,
  canUndo,
  onRedo,
  onSave,
  onSnapshot,
  onUndo,
  resumes,
  saveStatus,
  selectedId,
  setSelectedId,
}: {
  busyKey: string;
  canRedo: boolean;
  canUndo: boolean;
  onRedo: () => void;
  onSave: () => void;
  onSnapshot: () => void;
  onUndo: () => void;
  resumes: Resume[];
  saveStatus: SaveStatus;
  selectedId: string;
  setSelectedId: (value: string) => void;
}) {
  return (
    <div className="rounded-lg border border-line bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2
            className="text-lg font-black text-foreground"
            id="editor-heading"
          >
            Structured editor
          </h2>
          <p className="mt-1 text-sm text-muted">
            {saveStatusLabel(saveStatus)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select
            aria-label="Resume"
            className="min-w-48"
            onChange={(event) => setSelectedId(event.target.value)}
            value={selectedId}
          >
            {resumes.map((resume) => (
              <option key={resume.id} value={resume.id}>
                {resume.title}
              </option>
            ))}
          </Select>
          <IconButton disabled={!canUndo} label="Undo edit" onClick={onUndo}>
            <Undo2 aria-hidden="true" className="size-4" />
          </IconButton>
          <IconButton disabled={!canRedo} label="Redo edit" onClick={onRedo}>
            <Redo2 aria-hidden="true" className="size-4" />
          </IconButton>
          <Button
            disabled={saveStatus === "saving"}
            loading={busyKey === "save"}
            onClick={onSave}
            type="button"
            variant="secondary"
          >
            <Save aria-hidden="true" className="size-4" />
            Save
          </Button>
          <Button
            disabled={saveStatus === "saving"}
            loading={busyKey === "version"}
            onClick={onSnapshot}
            type="button"
          >
            <History aria-hidden="true" className="size-4" />
            Version
          </Button>
        </div>
      </div>
    </div>
  );
}

function ResumeFields({
  changeDraft,
  draft,
  sourceOptions,
}: {
  changeDraft: (transform: (current: ResumeDraft) => ResumeDraft) => void;
  draft: ResumeDraft;
  sourceOptions: ResumeSourceOptions | undefined;
}) {
  return (
    <section
      aria-label="Resume fields and layout"
      className="grid gap-4 rounded-lg border border-line bg-white p-4 shadow-sm lg:grid-cols-2"
    >
      <div className="grid gap-3">
        <label className="grid gap-1 text-sm font-bold text-foreground">
          Resume title
          <Input
            maxLength={120}
            onChange={(event) =>
              changeDraft((current) => ({
                ...current,
                title: event.target.value,
              }))
            }
            value={draft.title}
          />
        </label>
        <label className="grid gap-1 text-sm font-bold text-foreground">
          Target role
          <Input
            maxLength={120}
            onChange={(event) =>
              changeDraft((current) => ({
                ...current,
                targetRole: event.target.value,
              }))
            }
            value={draft.targetRole}
          />
        </label>
        <label className="grid gap-1 text-sm font-bold text-foreground">
          Template
          <Select
            onChange={(event) =>
              changeDraft((current) => ({
                ...current,
                template: event.target.value as TemplateValue,
              }))
            }
            value={draft.template}
          >
            {templates.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </label>
        <fieldset className="rounded-lg border border-line p-3">
          <legend className="px-1 text-sm font-bold text-foreground">
            Contact fields
          </legend>
          <div className="mt-1 grid gap-2">
            {sourceOptions?.personalFacts.map((fact) => {
              const requiredName = fact.kind === "name" && fact.isPrimary;
              return (
                <label className="flex items-start gap-2 text-sm" key={fact.id}>
                  <input
                    checked={draft.personalFactIds.includes(fact.id)}
                    className="mt-1"
                    disabled={requiredName}
                    onChange={(event) =>
                      changeDraft((current) => ({
                        ...current,
                        personalFactIds: event.target.checked
                          ? [...new Set([...current.personalFactIds, fact.id])]
                          : current.personalFactIds.filter(
                              (value) => value !== fact.id,
                            ),
                      }))
                    }
                    type="checkbox"
                  />
                  <span>
                    <span className="font-semibold">{fact.value}</span>
                    <span className="ml-2 text-xs text-muted">{fact.kind}</span>
                  </span>
                </label>
              );
            }) ?? (
              <p className="text-sm text-muted">Loading eligible fields…</p>
            )}
          </div>
        </fieldset>
      </div>

      <fieldset className="grid content-start gap-3 rounded-lg border border-line p-3">
        <legend className="px-1 text-sm font-bold text-foreground">
          Page layout
        </legend>
        <div className="grid gap-3 sm:grid-cols-2">
          <LayoutSelect
            label="Page size"
            onChange={(value) =>
              changeDraft((current) => ({
                ...current,
                layout: {
                  ...current.layout,
                  pageSize: value as ResumeDraft["layout"]["pageSize"],
                },
              }))
            }
            options={[
              ["letter", "US Letter"],
              ["a4", "A4"],
            ]}
            value={draft.layout.pageSize}
          />
          <LayoutSelect
            label="Page limit"
            onChange={(value) =>
              changeDraft((current) => ({
                ...current,
                layout: {
                  ...current.layout,
                  pageLimit: Number(value) as 1 | 2,
                },
              }))
            }
            options={[
              ["1", "One page"],
              ["2", "Two pages"],
            ]}
            value={String(draft.layout.pageLimit)}
          />
          <LayoutSelect
            label="Font"
            onChange={(value) =>
              changeDraft((current) => ({
                ...current,
                layout: {
                  ...current.layout,
                  fontFamily: value as ResumeDraft["layout"]["fontFamily"],
                },
              }))
            }
            options={[
              ["sans", "Sans serif"],
              ["serif", "Serif"],
            ]}
            value={draft.layout.fontFamily}
          />
          <label className="grid gap-1 text-sm font-semibold">
            Font size
            <Select
              onChange={(event) =>
                changeDraft((current) => ({
                  ...current,
                  layout: {
                    ...current.layout,
                    fontSizePt: Number(event.target.value),
                  },
                }))
              }
              value={String(draft.layout.fontSizePt)}
            >
              {[9, 10, 11, 12].map((size) => (
                <option key={size} value={size}>
                  {size} pt
                </option>
              ))}
            </Select>
          </label>
          <LayoutSelect
            label="Line spacing"
            onChange={(value) =>
              changeDraft((current) => ({
                ...current,
                layout: {
                  ...current.layout,
                  lineSpacing: value as ResumeDraft["layout"]["lineSpacing"],
                },
              }))
            }
            options={[
              ["compact", "Compact"],
              ["standard", "Standard"],
              ["relaxed", "Relaxed"],
            ]}
            value={draft.layout.lineSpacing}
          />
          <LayoutSelect
            label="Margins"
            onChange={(value) =>
              changeDraft((current) => ({
                ...current,
                layout: {
                  ...current.layout,
                  margins: value as ResumeDraft["layout"]["margins"],
                },
              }))
            }
            options={[
              ["narrow", "Narrow"],
              ["standard", "Standard"],
              ["wide", "Wide"],
            ]}
            value={draft.layout.margins}
          />
        </div>
      </fieldset>
    </section>
  );
}

function StructuredSections({
  addGroundedBullet,
  addSection,
  draft,
  moveBullet,
  moveSection,
  removeBullet,
  removeSection,
  replaceGroundedBullet,
  setSourceChoice,
  sourceChoice,
  sourceOptions,
  updateSection,
}: {
  addGroundedBullet: (sectionId: string) => void;
  addSection: () => void;
  changeDraft: (transform: (current: ResumeDraft) => ResumeDraft) => void;
  draft: ResumeDraft;
  moveBullet: (sectionId: string, index: number, direction: -1 | 1) => void;
  moveSection: (index: number, direction: -1 | 1) => void;
  removeBullet: (sectionId: string, bulletId: string) => void;
  removeSection: (sectionId: string) => void;
  replaceGroundedBullet: (
    sectionId: string,
    bulletId: string,
    sourceIndex: number,
  ) => void;
  setSourceChoice: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  sourceChoice: Record<string, string>;
  sourceOptions: ResumeSourceOptions | undefined;
  updateSection: (
    sectionId: string,
    patch: Partial<Pick<DraftSection, "kind" | "title">>,
  ) => void;
}) {
  return (
    <section
      aria-label="Resume sections"
      className="rounded-lg border border-line bg-white p-4 shadow-sm"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-black text-foreground">
            Sections and grounded bullets
          </h2>
          <p className="text-xs text-muted">
            New claims must come from an eligible source option.
          </p>
        </div>
        <Button onClick={addSection} type="button" variant="secondary">
          <Plus aria-hidden="true" className="size-4" />
          Section
        </Button>
      </div>
      <div className="space-y-3">
        {draft.sections.map((section, sectionIndex) => (
          <article
            className="rounded-lg border border-line bg-slate-50 p-3"
            key={section.id}
          >
            <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_10rem_auto]">
              <Input
                aria-label={`Section ${sectionIndex + 1} title`}
                maxLength={80}
                onChange={(event) =>
                  updateSection(section.id, { title: event.target.value })
                }
                value={section.title}
              />
              <Input
                aria-label={`${section.title} kind`}
                maxLength={40}
                onChange={(event) =>
                  updateSection(section.id, { kind: event.target.value })
                }
                value={section.kind}
              />
              <div className="flex gap-1">
                <IconButton
                  disabled={sectionIndex === 0}
                  label={`Move ${section.title} up`}
                  onClick={() => moveSection(sectionIndex, -1)}
                >
                  <ArrowUp aria-hidden="true" className="size-4" />
                </IconButton>
                <IconButton
                  disabled={sectionIndex === draft.sections.length - 1}
                  label={`Move ${section.title} down`}
                  onClick={() => moveSection(sectionIndex, 1)}
                >
                  <ArrowDown aria-hidden="true" className="size-4" />
                </IconButton>
                <IconButton
                  disabled={draft.sections.length === 1}
                  label={`Delete ${section.title}`}
                  onClick={() => removeSection(section.id)}
                >
                  <Trash2 aria-hidden="true" className="size-4" />
                </IconButton>
              </div>
            </div>

            <ol className="mt-3 space-y-2">
              {section.items.map((item, itemIndex) => {
                const matchingSource = sourceOptions?.bullets.findIndex(
                  (source) =>
                    source.text === item.text &&
                    source.source === item.source &&
                    source.entityId === item.entityId,
                );
                return (
                  <li
                    className="rounded-md border border-line bg-white p-2"
                    key={item.id}
                  >
                    <p className="text-sm text-foreground">{item.text}</p>
                    <div className="mt-2 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                      <Select
                        aria-label={`Grounded source for bullet ${itemIndex + 1} in ${section.title}`}
                        onChange={(event) =>
                          replaceGroundedBullet(
                            section.id,
                            item.id,
                            Number(event.target.value),
                          )
                        }
                        value={
                          matchingSource !== undefined && matchingSource >= 0
                            ? String(matchingSource)
                            : ""
                        }
                      >
                        {matchingSource === -1 && (
                          <option value="">Pinned approved claim</option>
                        )}
                        {sourceOptions?.bullets.map((source, index) => (
                          <option key={`${source.text}-${index}`} value={index}>
                            {source.text}
                          </option>
                        ))}
                      </Select>
                      <div className="flex gap-1">
                        <IconButton
                          disabled={itemIndex === 0}
                          label={`Move bullet ${itemIndex + 1} up`}
                          onClick={() => moveBullet(section.id, itemIndex, -1)}
                        >
                          <ArrowUp aria-hidden="true" className="size-4" />
                        </IconButton>
                        <IconButton
                          disabled={itemIndex === section.items.length - 1}
                          label={`Move bullet ${itemIndex + 1} down`}
                          onClick={() => moveBullet(section.id, itemIndex, 1)}
                        >
                          <ArrowDown aria-hidden="true" className="size-4" />
                        </IconButton>
                        <IconButton
                          label={`Delete bullet ${itemIndex + 1}`}
                          onClick={() => removeBullet(section.id, item.id)}
                        >
                          <Trash2 aria-hidden="true" className="size-4" />
                        </IconButton>
                      </div>
                    </div>
                    <p className="mt-1 text-xs text-muted">
                      {item.evidenceIds.length} evidence reference
                      {item.evidenceIds.length === 1 ? "" : "s"}
                    </p>
                  </li>
                );
              })}
            </ol>

            <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
              <Select
                aria-label={`Eligible claim for ${section.title}`}
                disabled={!sourceOptions?.bullets.length}
                onChange={(event) =>
                  setSourceChoice((current) => ({
                    ...current,
                    [section.id]: event.target.value,
                  }))
                }
                value={sourceChoice[section.id] ?? "0"}
              >
                {sourceOptions?.bullets.map((source, index) => (
                  <option key={`${source.text}-${index}`} value={index}>
                    {source.text}
                  </option>
                ))}
              </Select>
              <Button
                disabled={!sourceOptions?.bullets.length}
                onClick={() => addGroundedBullet(section.id)}
                type="button"
                variant="secondary"
              >
                <Plus aria-hidden="true" className="size-4" />
                Grounded bullet
              </Button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function Preview({
  draft,
  mode,
  setMode,
  sourceOptions,
}: {
  draft: ResumeDraft;
  mode: PreviewMode;
  setMode: (mode: PreviewMode) => void;
  sourceOptions: ResumeSourceOptions | undefined;
}) {
  const plainText = draftPlainText(draft, sourceOptions?.personalFacts ?? []);
  return (
    <section
      aria-label="Resume preview"
      className="rounded-lg border border-line bg-white p-4 shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-black text-foreground">Preview</h2>
        <div aria-label="Preview mode" className="flex gap-1" role="group">
          <PreviewButton
            active={mode === "page"}
            label="Page preview"
            onClick={() => setMode("page")}
          >
            <Eye aria-hidden="true" className="size-4" />
          </PreviewButton>
          <PreviewButton
            active={mode === "plain"}
            label="Plain text preview"
            onClick={() => setMode("plain")}
          >
            <FileText aria-hidden="true" className="size-4" />
          </PreviewButton>
          <PreviewButton
            active={mode === "recruiter"}
            label="Recruiter preview"
            onClick={() => setMode("recruiter")}
          >
            <Columns3 aria-hidden="true" className="size-4" />
          </PreviewButton>
        </div>
      </div>
      {mode === "page" ? (
        <article
          className={cn(
            "mx-auto mt-3 min-h-[38rem] max-w-[42rem] border border-slate-300 bg-white text-slate-950 shadow-md",
            draft.layout.fontFamily === "serif" ? "font-serif" : "font-sans",
            draft.layout.margins === "narrow"
              ? "p-6"
              : draft.layout.margins === "wide"
                ? "p-12"
                : "p-9",
            draft.layout.lineSpacing === "compact"
              ? "leading-tight"
              : draft.layout.lineSpacing === "relaxed"
                ? "leading-relaxed"
                : "leading-normal",
          )}
          style={{ fontSize: `${draft.layout.fontSizePt}pt` }}
        >
          <h3 className="text-center text-xl font-bold">
            {sourceOptions?.personalFacts.find(
              (fact) =>
                fact.kind === "name" && draft.personalFactIds.includes(fact.id),
            )?.value ?? draft.title}
          </h3>
          <p className="mt-1 text-center">
            {sourceOptions?.personalFacts
              .filter(
                (fact) =>
                  fact.kind !== "name" &&
                  draft.personalFactIds.includes(fact.id),
              )
              .map((fact) => fact.value)
              .join(" · ")}
          </p>
          {draft.targetRole && (
            <p className="mt-2 text-center font-semibold">{draft.targetRole}</p>
          )}
          {draft.sections.map((section) => (
            <section className="mt-4" key={section.id}>
              <h4 className="border-b border-slate-700 font-bold uppercase tracking-wide">
                {section.title}
              </h4>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {section.items.map((item) => (
                  <li key={item.id}>{item.text}</li>
                ))}
              </ul>
            </section>
          ))}
        </article>
      ) : mode === "plain" ? (
        <pre className="mt-3 max-h-[40rem] overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-4 text-sm leading-6 text-white">
          {plainText}
        </pre>
      ) : (
        <div className="mt-3 space-y-3 rounded-lg bg-slate-950 p-4 text-white">
          <p className="text-xs font-bold uppercase tracking-widest text-slate-300">
            Recruiter scan
          </p>
          <p className="text-lg font-black">
            {draft.targetRole || draft.title}
          </p>
          {draft.sections.map((section) => (
            <div key={section.id}>
              <p className="text-xs font-bold uppercase text-slate-300">
                {section.title}
              </p>
              <p className="mt-1 text-sm">
                {section.items.map((item) => item.text).join(" • ")}
              </p>
            </div>
          ))}
        </div>
      )}
      <p className="mt-3 text-xs text-muted">
        {draft.layout.pageSize.toUpperCase()} · {draft.layout.pageLimit} page
        {draft.layout.pageLimit === 1 ? "" : "s"} · {draft.layout.fontSizePt} pt
      </p>
    </section>
  );
}

function ExportPanel({
  busyKey,
  downloadUrl,
  exportRecord,
  format,
  onDownload,
  onDelete,
  onExport,
  selected,
  setFormat,
}: {
  busyKey: string;
  downloadUrl: string | undefined;
  exportRecord: ResumeExportRecord | undefined;
  format: FormatValue;
  onDownload: () => void;
  onDelete: () => void;
  onExport: () => void;
  selected: Resume | undefined;
  setFormat: (value: FormatValue) => void;
}) {
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const status = exportRecord?.export.status;
  return (
    <section
      aria-labelledby="export-heading"
      className="rounded-lg border border-line bg-white p-4 shadow-sm"
    >
      <h2 className="text-lg font-black text-foreground" id="export-heading">
        Verified export
      </h2>
      <div className="mt-4 grid gap-2 sm:grid-cols-[1fr_auto] 2xl:grid-cols-1">
        <Select
          aria-label="Export format"
          onChange={(event) => setFormat(event.target.value as FormatValue)}
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
          onClick={onExport}
          type="button"
        >
          <CheckCircle2 aria-hidden="true" className="size-4" />
          Verify
        </Button>
      </div>

      {exportRecord && (
        <div className="mt-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <Badge tone={exportTone(exportRecord)}>
              {status?.replaceAll("_", " ")}
            </Badge>
            <span className="text-xs text-muted">
              attempt {exportRecord.export.attempts}/
              {exportRecord.export.maxAttempts}
            </span>
          </div>
          {status === "deletion_pending" ||
          status === "deleting" ||
          status === "deletion_retry_wait" ? (
            <Alert title="Deleting" tone="info">
              Private-object cleanup is running in the background.
            </Alert>
          ) : status === "deletion_dead_lettered" ? (
            <Alert title="Cleanup needs attention" tone="danger">
              The private object is retained for safe operator recovery and no
              download is available.
            </Alert>
          ) : status === "deleted" ? (
            <Alert title="Deleted" tone="success">
              The generated file is gone. Immutable resume history is unchanged.
            </Alert>
          ) : status === "pending" ||
            status === "rendering" ||
            status === "retry_wait" ? (
            <Alert title="Processing" tone="info">
              Rendering and independent round-trip verification are running in
              the background.
            </Alert>
          ) : exportRecord.verification?.criticalFailures.length ? (
            <Alert title="Blocked" tone="danger">
              {exportRecord.verification.criticalFailures.join(", ")}
            </Alert>
          ) : exportRecord.verification?.warnings.length ? (
            <Alert title="Warnings" tone="warning">
              {exportRecord.verification.warnings.join(", ")}
            </Alert>
          ) : status === "verified" ? (
            <Alert title="Fidelity verified" tone="success">
              Exact occurrences, reading order, page limit, grounding, and
              searchability passed.
            </Alert>
          ) : (
            <Alert title="Not downloadable" tone="danger">
              The durable export did not produce a verified artifact.
            </Alert>
          )}
          {exportRecord.verification && (
            <dl className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <dt className="text-muted">Pages</dt>
                <dd className="font-bold">
                  {exportRecord.verification.pageCount}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Bytes</dt>
                <dd className="font-bold">{exportRecord.export.sizeBytes}</dd>
              </div>
            </dl>
          )}
          <Button
            disabled={status !== "verified"}
            loading={busyKey === "download"}
            onClick={onDownload}
            type="button"
            variant="secondary"
          >
            <Download aria-hidden="true" className="size-4" />
            Download
          </Button>
          {status !== "deleted" && (
            <Button
              disabled={
                status === "deletion_pending" ||
                status === "deleting" ||
                status === "deletion_retry_wait"
              }
              onClick={() => setConfirmingDelete(true)}
              type="button"
              variant="secondary"
            >
              <Trash2 aria-hidden="true" className="size-4" />
              Delete export
            </Button>
          )}
          {confirmingDelete && status !== "deleted" && (
            <Alert title="Confirm export deletion" tone="warning">
              <p>
                Delete only the generated file. The immutable resume version and
                verification history remain.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  onClick={() => setConfirmingDelete(false)}
                  type="button"
                  variant="secondary"
                >
                  Cancel
                </Button>
                <Button
                  loading={busyKey === "delete-export"}
                  onClick={() => {
                    setConfirmingDelete(false);
                    onDelete();
                  }}
                  type="button"
                >
                  Confirm delete export
                </Button>
              </div>
            </Alert>
          )}
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
  );
}

function HistoryPanel({
  busyKey,
  compareVersionId,
  comparison,
  current,
  onRestore,
  setCompareVersionId,
  versions,
}: {
  busyKey: string;
  compareVersionId: string;
  comparison: ResumeVersion | undefined;
  current: ResumeVersion | undefined;
  onRestore: (versionId: string) => void;
  setCompareVersionId: (value: string) => void;
  versions: ResumeVersion[];
}) {
  const diff =
    current && comparison
      ? changedLines(current.plainText, comparison.plainText)
      : undefined;
  return (
    <section
      aria-labelledby="history-heading"
      className="rounded-lg border border-line bg-white p-4 shadow-sm"
    >
      <h2 className="text-lg font-black text-foreground" id="history-heading">
        Immutable history
      </h2>
      <label className="mt-3 grid gap-1 text-sm font-semibold">
        Compare current with
        <Select
          onChange={(event) => setCompareVersionId(event.target.value)}
          value={compareVersionId}
        >
          <option value="">Choose a version</option>
          {versions.map((version) => (
            <option key={version.id} value={version.id}>
              Version {version.versionNumber}
            </option>
          ))}
        </Select>
      </label>
      {diff && (
        <div className="mt-3 grid gap-2 text-xs">
          <DiffList
            label="Only in current"
            lines={diff.currentOnly}
            tone="success"
          />
          <DiffList
            label={`Only in version ${comparison?.versionNumber ?? ""}`}
            lines={diff.comparisonOnly}
            tone="warning"
          />
        </div>
      )}
      <div className="mt-4 space-y-2">
        {versions.length === 0 ? (
          <p className="text-sm text-muted">No versions</p>
        ) : (
          versions
            .slice()
            .reverse()
            .map((version) => (
              <div
                className={cn(
                  "flex items-center justify-between gap-3 rounded-lg border border-line p-3",
                  current?.id === version.id && "bg-primary-soft",
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
                  disabled={current?.id === version.id}
                  label={`Restore version ${version.versionNumber}`}
                  loading={busyKey === `restore-${version.id}`}
                  onClick={() => onRestore(version.id)}
                >
                  <RotateCcw aria-hidden="true" className="size-4" />
                </IconButton>
              </div>
            ))
        )}
      </div>
    </section>
  );
}

function LayoutSelect({
  label,
  onChange,
  options,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  options: ReadonlyArray<readonly [string, string]>;
  value: string;
}) {
  return (
    <label className="grid gap-1 text-sm font-semibold">
      {label}
      <Select onChange={(event) => onChange(event.target.value)} value={value}>
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </Select>
    </label>
  );
}

function PreviewButton({
  active,
  children,
  label,
  onClick,
}: {
  active: boolean;
  children: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-label={label}
      aria-pressed={active}
      className={cn(
        "grid size-9 place-items-center rounded-lg border focus:outline-none focus:ring-3 focus:ring-primary-soft",
        active
          ? "border-primary bg-primary text-white"
          : "border-line bg-white text-muted",
      )}
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  );
}

function DiffList({
  label,
  lines,
  tone,
}: {
  label: string;
  lines: string[];
  tone: "success" | "warning";
}) {
  return (
    <div
      className={cn(
        "rounded-lg border p-2",
        tone === "success"
          ? "border-emerald-200 bg-emerald-50"
          : "border-amber-200 bg-amber-50",
      )}
    >
      <p className="font-bold">{label}</p>
      {lines.length ? (
        <ul className="mt-1 list-disc pl-4">
          {lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-muted">No line changes</p>
      )}
    </div>
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
      className="grid size-9 shrink-0 place-items-center rounded-lg border border-line bg-white text-muted shadow-sm transition hover:border-primary hover:text-primary focus:outline-none focus:ring-3 focus:ring-primary-soft disabled:cursor-not-allowed disabled:opacity-50"
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

function saveStatusLabel(status: SaveStatus): string {
  if (status === "saving") return "Saving draft…";
  if (status === "saved") return "All changes saved";
  if (status === "unsaved") return "Unsaved changes";
  if (status === "conflict") return "Conflict — local draft preserved";
  return "Autosave is ready";
}

function exportTone(
  record: ResumeExportRecord,
): "danger" | "neutral" | "success" | "warning" {
  if (
    record.export.status === "blocked" ||
    record.export.status === "failed" ||
    record.export.status === "dead_lettered" ||
    record.export.status === "deletion_dead_lettered"
  ) {
    return "danger";
  }
  if (record.export.status === "verified") {
    return record.export.verificationStatus === "warning"
      ? "warning"
      : "success";
  }
  return "neutral";
}

function appendVersion(
  versions: ResumeVersion[],
  version: ResumeVersion,
): ResumeVersion[] {
  return versions.some((item) => item.id === version.id)
    ? versions
    : [...versions, version];
}

function replaceResumeState(
  setResumes: React.Dispatch<React.SetStateAction<Resume[]>>,
  next: Resume,
) {
  setResumes((items) =>
    items.map((item) => (item.id === next.id ? next : item)),
  );
}

async function delay(milliseconds: number): Promise<void> {
  await new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function ResumeBuilderLoading() {
  return (
    <main
      className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8"
      id="main-content"
    >
      <LoadingSkeleton />
    </main>
  );
}
