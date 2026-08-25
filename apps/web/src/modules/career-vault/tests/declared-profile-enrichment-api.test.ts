import { afterEach, describe, expect, it, vi } from "vitest";

import {
  enqueuePersonalFactEnrichment,
  getPersonalFactEnrichmentJob,
} from "../api/career-vault-api";
import type { PersonalFact } from "../api/types";

const request = vi.hoisted(() => ({ mutation: vi.fn(), query: vi.fn() }));

vi.mock("@/shared/api/browser-request", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/shared/api/browser-request")>()),
  apiMutation: request.mutation,
  apiQuery: request.query,
}));

const fact = {
  id: "00000000-0000-4000-8000-000000000501",
  kind: "link",
  version: 1,
} as PersonalFact;

const jobPayload = {
  attempts: 0,
  errorMessage: null,
  jobId: "00000000-0000-4000-8000-000000000502",
  maxAttempts: 3,
  personalFactId: fact.id,
  resultAchievementsCreated: null,
  resultEvidenceCreated: null,
  resultPlatform: null,
  status: "queued",
};

describe("declared profile enrichment job API", () => {
  afterEach(() => {
    request.mutation.mockReset();
    request.query.mockReset();
  });

  it("enqueues enrichment with an idempotency key and parses the queued job", async () => {
    request.mutation.mockResolvedValue(
      new Response(JSON.stringify(jobPayload), { status: 202 }),
    );

    const job = await enqueuePersonalFactEnrichment(fact);

    expect(job.status).toBe("queued");
    expect(job.jobId).toBe(jobPayload.jobId);
    const init = request.mutation.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(init.headers).get("Idempotency-Key")).toBeTruthy();
  });

  it("polls job status by fact and job id", async () => {
    request.query.mockResolvedValue(
      new Response(
        JSON.stringify({ ...jobPayload, status: "succeeded" }),
        { status: 200 },
      ),
    );

    const job = await getPersonalFactEnrichmentJob(fact, jobPayload.jobId);

    expect(job.status).toBe("succeeded");
    const path = request.query.mock.calls[0]?.[0] as string;
    expect(path).toBe(
      `/api/v1/personal-facts/${fact.id}/enrich/${jobPayload.jobId}`,
    );
  });

  it("rejects a malformed job status response", async () => {
    request.query.mockResolvedValue(
      new Response(JSON.stringify({ ...jobPayload, status: "bogus" }), {
        status: 200,
      }),
    );

    await expect(
      getPersonalFactEnrichmentJob(fact, jobPayload.jobId),
    ).rejects.toThrow("Invalid declared profile enrichment job status");
  });
});
