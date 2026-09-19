"use client";

import { apiQuery } from "@/shared/api/browser-request";

import { buildReadinessSnapshot } from "../lib/readiness";
import type { ResumeBuilderReadinessSnapshot } from "../lib/readiness";
import { resumeBuilderReadinessPaths } from "./readiness-paths";
import { getSourceOptions } from "./resume-builder-api";

type ListPayload = {
  data?: unknown[];
};

async function readList(path: Parameters<typeof apiQuery>[0]): Promise<ListPayload | null> {
  try {
    const response = await apiQuery(path, { retryAfterRefresh: true });
    return (await response.json()) as ListPayload;
  } catch {
    return null;
  }
}

export async function loadResumeBuilderReadiness(): Promise<ResumeBuilderReadinessSnapshot> {
  const [sourceResult, evidencePayload, experiencesPayload, skillsPayload] =
    await Promise.all([
      getSourceOptions()
        .then((sourceOptions) => ({ sourceOptions }))
        .catch((error: unknown) => ({
          sourceError:
            error instanceof Error
              ? error.message
              : "Resume source preview could not load.",
        })),
      readList(resumeBuilderReadinessPaths.evidence),
      readList(resumeBuilderReadinessPaths.experiences),
      readList(resumeBuilderReadinessPaths.skills),
    ]);

  return buildReadinessSnapshot({
    evidencePayload,
    experiencesPayload,
    skillsPayload,
    ...sourceResult,
  });
}
