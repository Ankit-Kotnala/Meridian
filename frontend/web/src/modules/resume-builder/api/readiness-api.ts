"use client";

import { apiQuery } from "@/shared/api/browser-request";

import { buildReadinessSnapshot } from "../lib/readiness";
import type { ResumeBuilderReadinessSnapshot } from "../lib/readiness";
import { resumeBuilderReadinessPaths } from "./readiness-paths";
import { getSourceOptions } from "./resume-builder-api";

type ListPayload = {
  data?: unknown[];
};

async function readList(
  path: Parameters<typeof apiQuery>[0],
  options?: { cacheBust?: number },
): Promise<ListPayload | null> {
  try {
    const requestPath =
      options?.cacheBust === undefined
        ? path
        : (`${path}${path.includes("?") ? "&" : "?"}cacheBust=${options.cacheBust}` as Parameters<
            typeof apiQuery
          >[0]);
    const response = await apiQuery(requestPath, { retryAfterRefresh: true });
    return (await response.json()) as ListPayload;
  } catch {
    return null;
  }
}

export async function loadResumeBuilderReadiness(options?: {
  cacheBust?: boolean;
}): Promise<ResumeBuilderReadinessSnapshot> {
  const cacheBust = options?.cacheBust ? Date.now() : undefined;
  const [sourceResult, evidencePayload, experiencesPayload, skillsPayload] =
    await Promise.all([
      getSourceOptions(cacheBust)
        .then((sourceOptions) => ({ sourceOptions }))
        .catch((error: unknown) => ({
          sourceError:
            error instanceof Error
              ? error.message
              : "Resume source preview could not load.",
        })),
      readList(resumeBuilderReadinessPaths.evidence, { cacheBust }),
      readList(resumeBuilderReadinessPaths.experiences, { cacheBust }),
      readList(resumeBuilderReadinessPaths.skills, { cacheBust }),
    ]);

  return buildReadinessSnapshot({
    evidencePayload,
    experiencesPayload,
    skillsPayload,
    ...sourceResult,
  });
}
