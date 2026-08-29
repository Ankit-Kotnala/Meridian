"use client";

import { useCallback, useRef, useState, type FormEvent } from "react";

import { Alert, Button, ConfirmDialog, Select } from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  ApiRequestError,
  listApplicationSourceResumes,
  listApplicationSourceResumeVersions,
  updateApplication,
} from "../api/applications-api";
import type {
  ApplicationDetail,
  SavedResume,
  SavedResumeVersion,
} from "../api/types";
import { formatDate } from "./application-options";

type LoadState<T> =
  | { status: "idle" }
  | { status: "pending" }
  | { message: string; status: "error" }
  | { data: T; status: "success" };

export function ApplicationResumeChangePanel({
  application,
  onChange,
  onFailure,
  onSuccess,
}: {
  application: ApplicationDetail;
  onChange: (application: ApplicationDetail) => void;
  onFailure: (message: string, conflict: boolean) => void;
  onSuccess: (message: string) => void;
}) {
  const [resumeState, setResumeState] = useState<LoadState<SavedResume[]>>({
    status: "idle",
  });
  const [versionState, setVersionState] = useState<
    LoadState<SavedResumeVersion[]>
  >({ status: "idle" });
  const [resumeId, setResumeId] = useState(application.resumeId);
  const [versionId, setVersionId] = useState(application.resumeVersionId);
  const [reason, setReason] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const versionRequest = useRef(0);

  const loadVersions = useCallback(
    async (nextResumeId: string, preferredVersionId?: string) => {
      const requestId = ++versionRequest.current;
      setVersionState({ status: "pending" });
      try {
        const versions =
          await listApplicationSourceResumeVersions(nextResumeId);
        if (requestId !== versionRequest.current) return;
        setVersionState({ data: versions, status: "success" });
        setVersionId(
          versions.some((version) => version.id === preferredVersionId)
            ? preferredVersionId!
            : (versions[0]?.id ?? ""),
        );
      } catch (error) {
        if (requestId !== versionRequest.current) return;
        setVersionState({
          message: requestErrorMessage(
            error,
            "Resume versions could not be loaded.",
          ),
          status: "error",
        });
        setVersionId("");
      }
    },
    [],
  );

  const loadResumes = useCallback(async () => {
    setResumeState({ status: "pending" });
    try {
      const resumes = await listApplicationSourceResumes();
      setResumeState({ data: resumes, status: "success" });
      const nextResumeId = resumes.some(
        (resume) => resume.id === application.resumeId,
      )
        ? application.resumeId
        : (resumes[0]?.id ?? "");
      setResumeId(nextResumeId);
      if (nextResumeId) {
        void loadVersions(nextResumeId, application.resumeVersionId);
      } else {
        setVersionState({ data: [], status: "success" });
        setVersionId("");
      }
    } catch (error) {
      setResumeState({
        message: requestErrorMessage(error, "Resumes could not be loaded."),
        status: "error",
      });
    }
  }, [application.resumeId, application.resumeVersionId, loadVersions]);

  const resumes =
    resumeState.status === "success" ? resumeState.data : undefined;
  const versions =
    versionState.status === "success" ? versionState.data : undefined;
  const selectedResume = resumes?.find((resume) => resume.id === resumeId);
  const selectedVersion = versions?.find((version) => version.id === versionId);
  const unchanged = versionId === application.resumeVersionId;

  function review(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedVersion || unchanged || !reason.trim()) return;
    setConfirmOpen(true);
  }

  async function confirm() {
    if (!selectedVersion || unchanged || !reason.trim()) return;
    setBusy(true);
    try {
      const updated = await updateApplication(application, {
        resumeChangeReason: reason.trim(),
        resumeVersionId: selectedVersion.id,
      });
      setConfirmOpen(false);
      onChange(updated);
      onSuccess(
        `Pinned resume changed to ${selectedVersion.title}, version ${selectedVersion.versionNumber}.`,
      );
    } catch (error) {
      const conflict =
        error instanceof ApiRequestError &&
        (error.failure.status === 409 || error.failure.status === 412);
      setConfirmOpen(false);
      onFailure(
        conflict
          ? "This application changed in another session. Reload before changing its pinned resume."
          : requestErrorMessage(
              error,
              "The pinned resume version could not be changed.",
            ),
        conflict,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <details
        className="rounded-xl border border-line bg-surface shadow-sm"
        onToggle={(event) => {
          if (event.currentTarget.open && resumeState.status === "idle") {
            void loadResumes();
          }
        }}
      >
        <summary className="min-h-12 cursor-pointer list-none px-4 py-3 text-sm font-black text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary-soft">
          Change pinned resume version
        </summary>
        <div className="border-t border-line p-4">
          <Alert title="Material source change" tone="warning">
            Changing this pin replaces the application&apos;s resume claims and
            evidence snapshot. Existing generated packs remain attached to their
            original immutable pins. A reason and final confirmation are
            required.
          </Alert>

          {resumeState.status === "pending" && (
            <p className="mt-4 text-sm text-muted" role="status">
              Loading resumes...
            </p>
          )}
          {resumeState.status === "error" && (
            <Alert className="mt-4" title="Resumes unavailable" tone="danger">
              <p>{resumeState.message}</p>
              <Button
                className="mt-3 min-h-9 px-3"
                onClick={() => void loadResumes()}
                variant="secondary"
              >
                Retry resumes
              </Button>
            </Alert>
          )}
          {resumes?.length === 0 && (
            <Alert className="mt-4" title="No resumes available" tone="warning">
              Create a resume before changing this application&apos;s pin.
            </Alert>
          )}

          {resumes && resumes.length > 0 && (
            <form className="mt-4 grid gap-4" onSubmit={review}>
              <label className="text-sm font-bold text-foreground">
                Resume
                <Select
                  className="mt-1"
                  onChange={(event) => {
                    const nextResumeId = event.target.value;
                    setResumeId(nextResumeId);
                    void loadVersions(
                      nextResumeId,
                      nextResumeId === application.resumeId
                        ? application.resumeVersionId
                        : undefined,
                    );
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

              <label className="text-sm font-bold text-foreground">
                New immutable resume version
                <Select
                  aria-busy={versionState.status === "pending" || undefined}
                  className="mt-1"
                  disabled={!versions?.length}
                  onChange={(event) => setVersionId(event.target.value)}
                  value={versionId}
                >
                  {versionState.status === "pending" && (
                    <option value="">Loading resume versions...</option>
                  )}
                  {versions?.length === 0 && (
                    <option value="">No immutable versions available</option>
                  )}
                  {versions?.map((version) => (
                    <option key={version.id} value={version.id}>
                      {version.title}, version {version.versionNumber} —{" "}
                      {formatDate(version.createdAt)}
                    </option>
                  ))}
                </Select>
              </label>

              {versionState.status === "error" && (
                <Alert title="Resume versions unavailable" tone="danger">
                  <p>{versionState.message}</p>
                  <Button
                    className="mt-3 min-h-9 px-3"
                    onClick={() =>
                      void loadVersions(
                        resumeId,
                        resumeId === application.resumeId
                          ? application.resumeVersionId
                          : undefined,
                      )
                    }
                    variant="secondary"
                  >
                    Retry resume versions
                  </Button>
                </Alert>
              )}

              <label className="text-sm font-bold text-foreground">
                Reason for changing the pinned resume
                <textarea
                  className="mt-1 min-h-24 w-full resize-y rounded-xl border border-line bg-surface px-3.5 py-3 text-sm text-foreground shadow-sm outline-none focus:border-primary focus:ring-3 focus:ring-primary-soft"
                  maxLength={500}
                  onChange={(event) => setReason(event.target.value)}
                  required
                  value={reason}
                />
                <span className="mt-1 block text-xs font-normal text-muted">
                  Required for the immutable application audit trail. Maximum
                  500 characters.
                </span>
              </label>

              <Button
                disabled={!selectedVersion || unchanged || !reason.trim()}
                type="submit"
                variant="secondary"
              >
                Review resume version change
              </Button>
              {unchanged && selectedVersion && (
                <p className="text-xs text-muted">
                  Select a different immutable version to continue.
                </p>
              )}
            </form>
          )}
        </div>
      </details>

      <ConfirmDialog
        confirmLabel="Change pinned version"
        description={
          <>
            Replace <strong>{application.resumeTitle}</strong>, version{" "}
            {application.resumeVersionNumber}, with{" "}
            <strong>{selectedResume?.title ?? selectedVersion?.title}</strong>,
            version {selectedVersion?.versionNumber}? The recorded reason is:
            <span className="mt-2 block rounded-lg bg-surface-subtle p-3">
              {reason.trim()}
            </span>
          </>
        }
        loading={busy}
        onConfirm={() => void confirm()}
        onOpenChange={setConfirmOpen}
        open={confirmOpen}
        title="Confirm pinned resume change"
      />
    </>
  );
}
