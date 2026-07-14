import { z } from "zod";

export const readinessStateSchema = z.enum(["ready", "not_ready"]);
export const componentReadinessStateSchema = z.enum(["ok", "unavailable"]);

export const componentReadinessSchema = z.object({
  status: componentReadinessStateSchema,
});

export const healthResponseSchema = z.object({
  status: z.literal("ok"),
  service: z.string().min(1),
  version: z.string().min(1),
});

export const readinessResponseSchema = z.object({
  status: readinessStateSchema,
  service: z.string().min(1),
  version: z.string().min(1),
  checks: z.record(z.string(), componentReadinessSchema),
});

export const apiFieldErrorSchema = z.object({
  field: z.string().min(1),
  code: z.string().min(1),
  message: z.string().min(1),
});

export const apiErrorSchema = z.object({
  type: z.string().min(1),
  title: z.string().min(1),
  status: z.number().int().min(400).max(599),
  code: z.string().min(1),
  detail: z.string(),
  instance: z.string().optional(),
  requestId: z.string().min(1).max(128),
  errors: z.array(apiFieldErrorSchema).optional(),
});

export const cursorPageSchema = z.object({
  limit: z.number().int().min(1).max(100),
  nextCursor: z.string().min(1).nullable(),
  hasMore: z.boolean(),
});

export type HealthResponse = z.infer<typeof healthResponseSchema>;
export type ReadinessResponse = z.infer<typeof readinessResponseSchema>;
export type ApiFieldError = z.infer<typeof apiFieldErrorSchema>;
export type ApiError = z.infer<typeof apiErrorSchema>;
export type CursorPage = z.infer<typeof cursorPageSchema>;

export const CAREEROS_SCORE_DISCLAIMER =
  "CareerOS scores are internal readiness measurements. They are not scores provided by an employer or applicant tracking system and do not guarantee interviews or employment outcomes.";
