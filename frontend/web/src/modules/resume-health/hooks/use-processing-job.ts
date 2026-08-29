"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { requestErrorMessage } from "@/shared/api/browser-request";

import { getProcessingJob } from "../api/resume-health-api";
import type { ProcessingJob, ResumeHealthAccess } from "../api/types";
import { isProcessingJobTerminal } from "./processing-job-state";

export function useProcessingJob(access: ResumeHealthAccess, jobId: string) {
  const [job, setJob] = useState<ProcessingJob>();
  const [failure, setFailure] = useState<string>();
  const [revision, setRevision] = useState(0);
  const mounted = useRef(true);

  const retry = useCallback(() => {
    setFailure(undefined);
    setRevision((value) => value + 1);
  }, []);

  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let pollCount = 0;

    const poll = async () => {
      try {
        const next = await getProcessingJob(access, jobId, controller.signal);
        if (!mounted.current) return;
        setJob(next);
        setFailure(undefined);
        if (isProcessingJobTerminal(next)) return;
        pollCount += 1;
        const delay = Math.min(4_000, 750 + pollCount * 250);
        timer = setTimeout(() => void poll(), delay);
      } catch (error) {
        if (controller.signal.aborted || !mounted.current) return;
        setFailure(
          requestErrorMessage(
            error,
            "We couldn’t refresh the processing status.",
          ),
        );
      }
    };

    void poll();
    return () => {
      mounted.current = false;
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [access, jobId, revision]);

  return { failure, job, retry };
}
