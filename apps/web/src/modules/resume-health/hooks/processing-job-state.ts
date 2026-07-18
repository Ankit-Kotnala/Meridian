import type { ProcessingJob } from "../api/types";

type JobState = Pick<ProcessingJob, "error" | "status">;

export function isProcessingJobTerminal(job: JobState): boolean {
  if (job.status === "succeeded" || job.status === "cancelled") return true;
  if (job.status === "deadLettered") return true;
  return job.status === "failed" && job.error?.retryable !== true;
}
