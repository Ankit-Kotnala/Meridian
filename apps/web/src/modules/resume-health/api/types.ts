import type { components } from "@rezumi/contracts";

export type UploadPolicy = components["schemas"]["UploadPolicyResponse"];
export type UploadIntent = components["schemas"]["UploadIntentResponse"];
export type UploadIntentInput = components["schemas"]["UploadIntentRequest"];
export type FinalizeUpload = components["schemas"]["FinalizeUploadResponse"];
export type ProcessingJob = components["schemas"]["ProcessingJobResponse"];
export type DocumentSummary = components["schemas"]["DocumentSummaryResponse"];
export type DocumentDetail = components["schemas"]["DocumentResponse"];
export type DocumentList = components["schemas"]["DocumentListResponse"];
export type CanonicalResume = components["schemas"]["CanonicalResumeResponse"];
export type CanonicalSection =
  components["schemas"]["CanonicalSectionResponse"];
export type CanonicalField = components["schemas"]["CanonicalFieldResponse"];
export type CanonicalUpdate =
  components["schemas"]["CanonicalResumeUpdateRequest"];
export type SemanticEntity = components["schemas"]["SemanticEntityResponse"];
export type SemanticField = components["schemas"]["SemanticFieldResponse"];
export type SemanticReviewOperation = NonNullable<
  CanonicalUpdate["semanticOperations"]
>[number];
export type PlainText = components["schemas"]["PlainTextResponse"];
export type ReadingOrder = components["schemas"]["ReadingOrderResponse"];
export type ResumeHealthReport =
  components["schemas"]["ResumeHealthReportResponse"];
export type ResumeHealthComponent =
  components["schemas"]["ResumeHealthComponentResponse"];
export type ResumeHealthFeatureContribution =
  components["schemas"]["ResumeHealthFeatureContributionResponse"];
export type ResumeHealthFeatureValue =
  components["schemas"]["ResumeHealthFeatureValueResponse"];
export type ResumeFinding = components["schemas"]["ResumeFindingResponse"];
export type JobAccepted = components["schemas"]["JobAcceptedResponse"];
export type ClaimGuestDocument =
  components["schemas"]["ClaimGuestDocumentResponse"];

export type ResumeHealthAccess = "account" | "guest";
