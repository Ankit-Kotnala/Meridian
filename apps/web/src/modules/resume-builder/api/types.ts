import type { components } from "@rezumi/contracts";

export type Resume = components["schemas"]["ResumeResponse"];
export type ResumeCreateInput = components["schemas"]["ResumeCreateRequest"];
export type ResumeUpdateInput = components["schemas"]["ResumeUpdateRequest"];
export type ResumeVersion = components["schemas"]["ResumeVersionResponse"];
export type ResumeSectionResponse =
  components["schemas"]["ResumeSectionResponse"];
export type ResumeExportInput = components["schemas"]["ResumeExportRequest"];
export type ResumeExportRecord =
  components["schemas"]["ResumeExportRecordResponse"];
export type ResumeDownloadIntent =
  components["schemas"]["ResumeDownloadIntentResponse"];
