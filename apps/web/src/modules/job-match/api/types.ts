import type { components } from "@rezumi/contracts";

export type Job = components["schemas"]["JobResponse"];
export type JobPage = components["schemas"]["JobPageResponse"];
export type JobCatalogSearch = components["schemas"]["JobCatalogSearchResponse"];
export type JobCatalogListing =
  components["schemas"]["JobCatalogListingResponse"];
export type JobCatalogBrowse =
  components["schemas"]["JobCatalogBrowseResponse"];
export type RolePreference = components["schemas"]["RolePreferenceResponse"];
export type JobCreateInput = components["schemas"]["JobCreateRequest"];
export type JobImportInput = components["schemas"]["JobImportRequest"];
export type JobUpdateInput = components["schemas"]["JobUpdateRequest"];
export type JobMatchAnalysis =
  components["schemas"]["JobMatchAnalysisResponse"];
export type RequirementMatchPage =
  components["schemas"]["RequirementMatchPageResponse"];
export type OpportunityPriorityInput =
  components["schemas"]["OpportunityPriorityRequest"];
export type OpportunityPriority =
  components["schemas"]["OpportunityPriorityResponse"];
export type JobSourceKind = NonNullable<Job["sourceKind"]>;
export type WorkModel = NonNullable<Job["workModel"]>;
export type EmploymentType = NonNullable<Job["employmentType"]>;
export type PreferenceFit = NonNullable<
  OpportunityPriorityInput["compensationFit"]
>;
export type TailoringEffort = NonNullable<
  OpportunityPriorityInput["tailoringEffort"]
>;
