"use client";

import { Database, Download, FileArchive, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import { deleteAccount, exportAccountData } from "../api/settings-api";
import { useSettingsCapabilities } from "../components/settings-capabilities-context";

export function PrivacySettings() {
  const router = useRouter();
  const { capabilities, failure, loading, reload } = useSettingsCapabilities();
  const [exportBusy, setExportBusy] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [actionFailure, setActionFailure] = useState<string>();
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  if (loading && !capabilities) return <LoadingSkeleton variant="form" />;
  if (!capabilities) {
    return (
      <ErrorState
        description={failure ?? "We couldn’t load privacy capabilities."}
        onRetry={reload}
        title="Privacy settings unavailable"
      />
    );
  }

  const exportAvailable = capabilities.accountExportAvailable;
  const deletionAvailable = capabilities.accountDeletionAvailable;

  if (!exportAvailable && !deletionAvailable) {
    return (
      <EmptyState
        description="Account export and deletion are not enabled in this environment. Contact your administrator if you need these controls."
        title="Privacy controls unavailable"
      />
    );
  }

  const handleExportData = async () => {
    setExportBusy(true);
    setActionFailure(undefined);
    try {
      const data = await exportAccountData();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `rezumi-data-export-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      setActionFailure(
        requestErrorMessage(error, "Failed to export account data archive."),
      );
    } finally {
      setExportBusy(false);
    }
  };

  const handleDeleteAccount = async () => {
    setDeleteBusy(true);
    setActionFailure(undefined);
    try {
      await deleteAccount();
      setConfirmDeleteOpen(false);
      router.push("/login?message=account_deleted");
    } catch (error) {
      setActionFailure(requestErrorMessage(error, "Failed to delete account."));
    } finally {
      setDeleteBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      {actionFailure ? (
        <ErrorState
          description={actionFailure}
          onRetry={() => setActionFailure(undefined)}
          title="Privacy action failed"
        />
      ) : null}

      <Card className="p-5 sm:p-7">
        <div className="flex items-start gap-3">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
            <Database aria-hidden="true" className="size-5" />
          </span>
          <div>
            <h2 className="text-lg font-extrabold text-foreground">
              Retention and document control
            </h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
              Guest resume files expire after{" "}
              {capabilities.guestResumeRetentionHours} hours. Account resume
              documents remain owner-managed until you delete them.
            </p>
            <Link
              className="text-link mt-4 inline-flex text-sm"
              href="/resume-health/account"
            >
              Review or delete account resume documents
            </Link>
          </div>
        </div>
      </Card>

      {exportAvailable ? (
        <Card className="p-5 sm:p-7">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-start gap-3">
              <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-surface-subtle text-muted">
                <FileArchive aria-hidden="true" className="size-5" />
              </span>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-extrabold text-foreground">
                    Account data export (GDPR / CCPA)
                  </h2>
                  <Badge tone="success">Available</Badge>
                </div>
              </div>
            </div>

            <Button
              loading={exportBusy}
              onClick={handleExportData}
              variant="secondary"
            >
              <Download className="mr-2 size-4" /> Export My Data
            </Button>
          </div>
        </Card>
      ) : null}

      {deletionAvailable ? (
        <Card className="p-5 sm:p-7">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-start gap-3">
              <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-danger-soft text-danger">
                <Trash2 aria-hidden="true" className="size-5" />
              </span>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-extrabold text-foreground">
                    Delete account
                  </h2>
                  <Badge tone="danger">Irreversible</Badge>
                </div>
                <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
                  Permanently purge your profile, career evidence, tailored
                  resumes, and tracked applications. This action cannot be
                  undone.
                </p>
              </div>
            </div>

            <Button onClick={() => setConfirmDeleteOpen(true)} variant="danger">
              Delete Account
            </Button>
          </div>
        </Card>
      ) : null}

      <ConfirmDialog
        confirmLabel="Permanently Delete Account"
        description="Are you sure you want to delete your account? All career profile data, evidence links, and generated resumes will be permanently erased."
        loading={deleteBusy}
        onConfirm={handleDeleteAccount}
        onOpenChange={setConfirmDeleteOpen}
        open={confirmDeleteOpen}
        title="Delete Account"
      />
    </div>
  );
}
