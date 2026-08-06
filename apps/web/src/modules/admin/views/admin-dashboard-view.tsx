"use client";

import {
  Activity,
  CheckCircle,
  Database,
  RefreshCw,
  Server,
  Shield,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  ErrorState,
  LoadingSkeleton,
} from "@rezumi/ui";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  getAdminOverview,
  getDeadLetterJobs,
  retryDeadLetterJob,
  type AdminMetrics,
  type DeadLetterJob,
} from "../api/admin-api";

export function AdminDashboardView() {
  const [metrics, setMetrics] = useState<AdminMetrics>();
  const [deadLetters, setDeadLetters] = useState<DeadLetterJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<string>();
  const [retryBusy, setRetryBusy] = useState<string>();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [metricsData, jobs] = await Promise.all([
        getAdminOverview(),
        getDeadLetterJobs(),
      ]);
      setMetrics(metricsData);
      setDeadLetters(jobs);
      setFailure(undefined);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "Failed to load admin overview metrics."),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void loadData());
  }, [loadData]);

  const handleRetryJob = async (jobId: string) => {
    setRetryBusy(jobId);
    try {
      await retryDeadLetterJob(jobId);
      await loadData();
    } catch (error) {
      setFailure(
        requestErrorMessage(error, `Failed to re-enqueue job ${jobId}.`),
      );
    } finally {
      setRetryBusy(undefined);
    }
  };

  if (loading && !metrics) return <LoadingSkeleton variant="form" />;
  if (failure && !metrics)
    return (
      <ErrorState
        description={failure}
        onRetry={loadData}
        title="Admin dashboard unavailable"
      />
    );

  return (
    <div className="flex flex-col gap-6 p-6">
      <Card className="p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span className="grid size-11 place-items-center rounded-xl bg-foreground text-background">
              <Shield className="size-6" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-black text-foreground">
                  Admin Console & Platform Status
                </h1>
                <Badge tone="success">
                  {metrics?.environment.toUpperCase() ?? "DEV"}
                </Badge>
              </div>
              <p className="text-sm text-muted">
                System health, background queues, plan distributions, and
                dead-letter job control.
              </p>
            </div>
          </div>
          <Button onClick={loadData} variant="secondary">
            <RefreshCw className="mr-2 size-4" /> Refresh Status
          </Button>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-4">
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted">
              Platform Users
            </span>
            <Users className="size-4 text-muted" />
          </div>
          <p className="mt-2 text-3xl font-black text-foreground">
            {metrics?.activeUsersCount}
          </p>
          <p className="mt-1 text-xs text-success">Active accounts</p>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted">
              Total Resumes
            </span>
            <Database className="size-4 text-muted" />
          </div>
          <p className="mt-2 text-3xl font-black text-foreground">
            {metrics?.totalResumesCount}
          </p>
          <p className="mt-1 text-xs text-muted">Structured documents</p>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted">
              Tracked Applications
            </span>
            <Activity className="size-4 text-muted" />
          </div>
          <p className="mt-2 text-3xl font-black text-foreground">
            {metrics?.totalApplicationsCount}
          </p>
          <p className="mt-1 text-xs text-muted">Application packs pinned</p>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted">
              API Service Version
            </span>
            <Server className="size-4 text-muted" />
          </div>
          <p className="mt-2 text-2xl font-black text-foreground">
            {metrics?.serviceVersion}
          </p>
          <p className="mt-1 text-xs text-success">Healthy & operational</p>
        </Card>
      </div>

      <Card className="p-6">
        <h3 className="text-base font-bold text-foreground">
          Infrastructure Services Health
        </h3>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-4">
          {metrics &&
            Object.entries(metrics.systemHealth).map(([svc, status]) => (
              <div
                className="flex items-center justify-between rounded-xl border border-line bg-surface-subtle p-4"
                key={svc}
              >
                <span className="text-sm font-semibold capitalize text-muted-strong">
                  {svc.replace("_", " ")}
                </span>
                <span className="flex items-center gap-1.5 text-xs font-bold text-success-strong">
                  <CheckCircle className="size-4 text-success" /> {status}
                </span>
              </div>
            ))}
        </div>
      </Card>

      <Card className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-foreground">
              Dead-Letter Job Queue
            </h3>
            <p className="text-xs text-muted">
              Failed background worker tasks awaiting admin inspection or retry.
            </p>
          </div>
          <Badge tone={deadLetters.length === 0 ? "success" : "danger"}>
            {deadLetters.length} Dead Letters
          </Badge>
        </div>

        {deadLetters.length === 0 ? (
          <Alert className="mt-4" title="Queue is clean" tone="info">
            There are no failed or dead-lettered background jobs in the queue.
          </Alert>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b bg-surface-subtle text-muted">
                <tr>
                  <th className="p-3 font-semibold">Job ID</th>
                  <th className="p-3 font-semibold">Task Type</th>
                  <th className="p-3 font-semibold">Attempts</th>
                  <th className="p-3 font-semibold">Error</th>
                  <th className="p-3 font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {deadLetters.map((job) => (
                  <tr key={job.id}>
                    <td className="p-3 font-mono text-foreground">
                      {job.id.slice(0, 8)}...
                    </td>
                    <td className="p-3 font-medium text-foreground">
                      {job.jobType}
                    </td>
                    <td className="p-3">
                      {job.attempts} / {job.maxAttempts}
                    </td>
                    <td className="p-3 text-danger">
                      {job.lastError ?? "Worker error"}
                    </td>
                    <td className="p-3">
                      <Button
                        loading={retryBusy === job.id}
                        onClick={() => handleRetryJob(job.id)}
                        variant="secondary"
                      >
                        Re-enqueue
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

export type { AdminMetrics, DeadLetterJob };
