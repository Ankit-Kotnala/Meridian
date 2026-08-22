"use client";

import {
  ApiRequestError,
  apiMutation,
  apiQuery,
} from "@/shared/api/browser-request";

import {
  parseAchievement,
  parseAchievementPage,
  parseAttachmentDownloadIntent,
  parseAttachmentUploadIntent,
  parseCareerItem,
  parseCareerItems,
  parseCareerProfile,
  parseCareerRelationship,
  parseCareerRelationships,
  parseEvidence,
  parseEvidencePage,
  parseExperience,
  parseExperiences,
  parseProfileImportBatch,
  parseProfileImportProposal,
  parsePersonalFact,
  parsePersonalFacts,
  parseReminderPreferences,
  parseSkill,
  parseSkills,
} from "./contract-parsers";
import { careerVaultPaths, withQuery } from "./paths";
import type {
  Achievement,
  AchievementInput,
  AttachmentUploadIntent,
  CareerItem,
  CareerItemInput,
  CareerProfile,
  CareerProfileUpdate,
  CareerRelationship,
  EvidenceFilters,
  EvidenceInput,
  EvidenceItem,
  EvidenceUpdate,
  Experience,
  ExperienceInput,
  Page,
  PersonalFact,
  PersonalFactInput,
  ProfileImportBatch,
  ProfileImportProposal,
  ReminderPreferences,
  Skill,
  SkillInput,
} from "./types";

function headers(version?: number, idempotent = false): HeadersInit {
  return {
    ...(version === undefined ? {} : { "If-Match": `"${version}"` }),
    ...(idempotent ? { "Idempotency-Key": crypto.randomUUID() } : {}),
  };
}

async function query(path: Parameters<typeof apiQuery>[0]) {
  return apiQuery(path, { retryAfterRefresh: true });
}

async function mutate(
  path: Parameters<typeof apiMutation>[0],
  init: Parameters<typeof apiMutation>[1],
) {
  return apiMutation(path, init, { csrf: "session", retryAfterRefresh: true });
}

export async function getCareerProfile(): Promise<CareerProfile> {
  return parseCareerProfile(
    await (await query(careerVaultPaths.careerProfile)).json(),
  );
}

export async function updateCareerProfile(
  profile: CareerProfile,
  input: CareerProfileUpdate,
): Promise<CareerProfile> {
  const response = await mutate(careerVaultPaths.careerProfile, {
    body: JSON.stringify(input),
    headers: headers(profile.version),
    method: "PATCH",
  });
  return parseCareerProfile(await response.json());
}

export async function getPersonalFacts(): Promise<PersonalFact[]> {
  return parsePersonalFacts(
    await (await query(careerVaultPaths.personalFacts)).json(),
  );
}

export async function createPersonalFact(
  input: PersonalFactInput,
): Promise<PersonalFact> {
  const response = await mutate(careerVaultPaths.personalFacts, {
    body: JSON.stringify(input),
    headers: headers(undefined, true),
    method: "POST",
  });
  return parsePersonalFact(await response.json());
}

export async function updatePersonalFact(
  fact: PersonalFact,
  input: Omit<PersonalFactInput, "kind">,
): Promise<PersonalFact> {
  const response = await mutate(careerVaultPaths.personalFact(fact.id), {
    body: JSON.stringify(input),
    headers: headers(fact.version),
    method: "PATCH",
  });
  return parsePersonalFact(await response.json());
}

export async function confirmPersonalFact(
  fact: PersonalFact,
): Promise<PersonalFact> {
  const response = await mutate(careerVaultPaths.personalFactConfirm(fact.id), {
    headers: headers(fact.version),
    method: "POST",
  });
  return parsePersonalFact(await response.json());
}

export async function deletePersonalFact(fact: PersonalFact): Promise<void> {
  await mutate(careerVaultPaths.personalFact(fact.id), {
    headers: headers(fact.version, true),
    method: "DELETE",
  });
}

export type PersonalFactEnrichmentResult = {
  achievementsCreated: number;
  evidenceCreated: number;
  platform: string;
  profileUrl: string;
  skippedDuplicates: number;
};

export async function enrichPersonalFactLink(
  fact: PersonalFact,
): Promise<PersonalFactEnrichmentResult> {
  const response = await mutate(careerVaultPaths.personalFactEnrich(fact.id), {
    headers: headers(undefined, true),
    method: "POST",
  });
  const payload = (await response.json()) as Record<string, unknown>;
  return {
    achievementsCreated: Number(payload.achievementsCreated ?? 0),
    evidenceCreated: Number(payload.evidenceCreated ?? 0),
    platform: String(payload.platform ?? ""),
    profileUrl: String(payload.profileUrl ?? ""),
    skippedDuplicates: Number(payload.skippedDuplicates ?? 0),
  };
}

export async function getCareerRelationships(): Promise<CareerRelationship[]> {
  return parseCareerRelationships(
    await (await query(careerVaultPaths.careerRelationships)).json(),
  );
}

export async function createCareerRelationship(
  experienceId: string,
  projectId: string,
): Promise<CareerRelationship> {
  const response = await mutate(careerVaultPaths.careerRelationships, {
    body: JSON.stringify({
      experienceId,
      kind: "experience_project",
      projectId,
    }),
    headers: headers(undefined, true),
    method: "POST",
  });
  return parseCareerRelationship(await response.json());
}

export async function deleteCareerRelationship(
  relationship: CareerRelationship,
): Promise<void> {
  await mutate(careerVaultPaths.careerRelationship(relationship.id), {
    headers: headers(undefined, true),
    method: "DELETE",
  });
}

export async function getExperiences(
  options: { includeProvenance?: boolean } = {},
): Promise<Experience[]> {
  const requestPath =
    options.includeProvenance === false
      ? withQuery(careerVaultPaths.experiences, { includeProvenance: false })
      : careerVaultPaths.experiences;
  return parseExperiences(await (await query(requestPath)).json());
}

export async function createExperience(
  input: ExperienceInput,
): Promise<Experience> {
  const response = await mutate(careerVaultPaths.experiences, {
    body: JSON.stringify(input),
    headers: headers(undefined, true),
    method: "POST",
  });
  return parseExperience(await response.json());
}

export async function updateExperience(
  experience: Experience,
  input: ExperienceInput,
): Promise<Experience> {
  const response = await mutate(careerVaultPaths.experience(experience.id), {
    body: JSON.stringify(input),
    headers: headers(experience.version),
    method: "PATCH",
  });
  return parseExperience(await response.json());
}

export async function confirmExperience(
  experience: Experience,
): Promise<Experience> {
  const response = await mutate(
    careerVaultPaths.experienceConfirm(experience.id),
    {
      headers: headers(experience.version),
      method: "POST",
    },
  );
  return parseExperience(await response.json());
}

export async function deleteExperience(value: Experience): Promise<void> {
  await mutate(careerVaultPaths.experience(value.id), {
    headers: headers(value.version, true),
    method: "DELETE",
  });
}

export async function reorderExperiences(
  values: Experience[],
): Promise<Experience[]> {
  const response = await mutate(careerVaultPaths.experienceReorder, {
    body: JSON.stringify({
      items: values.map((item, position) => ({
        id: item.id,
        position,
        version: item.version,
      })),
    }),
    headers: headers(undefined, true),
    method: "POST",
  });
  return parseExperiences(await response.json());
}

export async function getCareerItems(): Promise<CareerItem[]> {
  return parseCareerItems(
    await (await query(careerVaultPaths.careerItems)).json(),
  );
}

export async function createCareerItem(
  input: CareerItemInput,
): Promise<CareerItem> {
  const response = await mutate(careerVaultPaths.careerItems, {
    body: JSON.stringify(input),
    headers: headers(undefined, true),
    method: "POST",
  });
  return parseCareerItem(await response.json());
}

export async function updateCareerItem(
  item: CareerItem,
  input: CareerItemInput,
): Promise<CareerItem> {
  const response = await mutate(careerVaultPaths.careerItem(item.id), {
    body: JSON.stringify(input),
    headers: headers(item.version),
    method: "PATCH",
  });
  return parseCareerItem(await response.json());
}

export async function confirmCareerItem(item: CareerItem): Promise<CareerItem> {
  const response = await mutate(careerVaultPaths.careerItemConfirm(item.id), {
    headers: headers(item.version),
    method: "POST",
  });
  return parseCareerItem(await response.json());
}

export async function deleteCareerItem(item: CareerItem): Promise<void> {
  await mutate(careerVaultPaths.careerItem(item.id), {
    headers: headers(item.version, true),
    method: "DELETE",
  });
}

export async function getSkills(
  options: { includeProvenance?: boolean } = {},
): Promise<Skill[]> {
  const requestPath =
    options.includeProvenance === false
      ? withQuery(careerVaultPaths.skills, { includeProvenance: false })
      : careerVaultPaths.skills;
  return parseSkills(await (await query(requestPath)).json());
}

export async function createSkill(input: SkillInput): Promise<Skill> {
  const response = await mutate(careerVaultPaths.skills, {
    body: JSON.stringify(input),
    headers: headers(undefined, true),
    method: "POST",
  });
  return parseSkill(await response.json());
}

export async function updateSkill(
  skill: Skill,
  input: SkillInput,
): Promise<Skill> {
  const response = await mutate(careerVaultPaths.skill(skill.id), {
    body: JSON.stringify(input),
    headers: headers(skill.version),
    method: "PATCH",
  });
  return parseSkill(await response.json());
}

export async function confirmSkill(skill: Skill): Promise<Skill> {
  const response = await mutate(careerVaultPaths.skillConfirm(skill.id), {
    headers: headers(skill.version),
    method: "POST",
  });
  return parseSkill(await response.json());
}

export async function deleteSkill(skill: Skill): Promise<void> {
  await mutate(careerVaultPaths.skill(skill.id), {
    headers: headers(skill.version, true),
    method: "DELETE",
  });
}

export async function getProfileImportProposal(
  id: string,
): Promise<ProfileImportProposal> {
  return parseProfileImportProposal(
    await (await query(careerVaultPaths.profileImportProposal(id))).json(),
  );
}

/** List every import proposal the account currently has, newest state included. */
export async function listProfileImportProposals(): Promise<
  ProfileImportProposal[]
> {
  const body: unknown = await (
    await query(careerVaultPaths.profileImportProposals)
  ).json();
  const data =
    typeof body === "object" && body !== null
      ? (body as { data?: unknown }).data
      : undefined;
  if (!Array.isArray(data)) {
    throw new Error("Invalid profile import proposal list response.");
  }
  return data.map(parseProfileImportProposal);
}

export async function createProfileImportProposals(
  documentId: string,
  snapshotId: string,
): Promise<ProfileImportBatch> {
  const response = await mutate(careerVaultPaths.profileImportProposals, {
    body: JSON.stringify({ documentId, snapshotId }),
    method: "POST",
  });
  return parseProfileImportBatch(await response.json());
}

export async function acceptProfileImportProposal(
  proposal: ProfileImportProposal,
  reviewedValues: Record<string, string>,
  idempotencyKey: string,
): Promise<ProfileImportProposal> {
  const values = Object.fromEntries(
    proposal.changes.map((change) => [
      change.id,
      reviewedValues[change.id] ?? change.proposedValue,
    ]),
  );
  const response = await mutate(
    careerVaultPaths.profileImportProposalAccept(proposal.id),
    {
      body: JSON.stringify({ values }),
      headers: {
        ...headers(proposal.version),
        "Idempotency-Key": idempotencyKey,
      },
      method: "POST",
    },
  );
  return parseProfileImportProposal(await response.json());
}

export async function rejectProfileImportProposal(
  proposal: ProfileImportProposal,
  idempotencyKey: string,
): Promise<ProfileImportProposal> {
  const response = await mutate(
    careerVaultPaths.profileImportProposalReject(proposal.id),
    {
      headers: {
        ...headers(proposal.version),
        "Idempotency-Key": idempotencyKey,
      },
      method: "POST",
    },
  );
  return parseProfileImportProposal(await response.json());
}

export async function getEvidence(
  filters: EvidenceFilters = {},
): Promise<Page<EvidenceItem>> {
  return parseEvidencePage(
    await (
      await query(
        withQuery(careerVaultPaths.evidence, {
          after: filters.after,
          archived: filters.archived,
          query: filters.query,
          state: filters.state,
        }),
      )
    ).json(),
  );
}

export async function getEvidenceItem(id: string): Promise<EvidenceItem> {
  return parseEvidence(
    await (await query(careerVaultPaths.evidenceItem(id))).json(),
  );
}

export async function createEvidence(
  input: EvidenceInput,
): Promise<EvidenceItem> {
  const response = await mutate(careerVaultPaths.evidence, {
    body: JSON.stringify(input),
    headers: headers(undefined, true),
    method: "POST",
  });
  return parseEvidence(await response.json());
}

export async function updateEvidence(
  evidence: EvidenceItem,
  input: EvidenceUpdate,
): Promise<EvidenceItem> {
  const response = await mutate(careerVaultPaths.evidenceItem(evidence.id), {
    body: JSON.stringify(input),
    headers: headers(evidence.version),
    method: "PATCH",
  });
  return parseEvidence(await response.json());
}

async function transitionEvidence(
  evidence: EvidenceItem,
  path: Parameters<typeof apiMutation>[0],
): Promise<EvidenceItem> {
  const response = await mutate(path, {
    headers: headers(evidence.version, true),
    method: "POST",
  });
  return parseEvidence(await response.json());
}

export function confirmEvidence(evidence: EvidenceItem) {
  return transitionEvidence(
    evidence,
    careerVaultPaths.evidenceConfirm(evidence.id),
  );
}

export function archiveEvidence(evidence: EvidenceItem) {
  return transitionEvidence(
    evidence,
    careerVaultPaths.evidenceArchive(evidence.id),
  );
}

export function restoreEvidence(evidence: EvidenceItem) {
  return transitionEvidence(
    evidence,
    careerVaultPaths.evidenceRestore(evidence.id),
  );
}

export function markEvidenceUnsupported(evidence: EvidenceItem) {
  return transitionEvidence(
    evidence,
    careerVaultPaths.evidenceUnsupported(evidence.id),
  );
}

export async function deleteEvidence(evidence: EvidenceItem): Promise<void> {
  await mutate(careerVaultPaths.evidenceItem(evidence.id), {
    headers: headers(evidence.version, true),
    method: "DELETE",
  });
}

export async function createAttachmentUploadIntent(
  evidence: EvidenceItem,
  file: File,
): Promise<AttachmentUploadIntent> {
  const response = await mutate(
    careerVaultPaths.evidenceAttachmentPresign(evidence.id),
    {
      body: JSON.stringify({
        displayFilename: file.name,
        expectedSizeBytes: file.size,
        mediaType: file.type,
      }),
      headers: headers(evidence.version, true),
      method: "POST",
    },
  );
  return parseAttachmentUploadIntent(await response.json());
}

function validatedPrivateObjectUrl(value: string): URL {
  const target = new URL(value);
  const configured = process.env.NEXT_PUBLIC_UPLOAD_ORIGIN;
  if (!configured || target.origin !== new URL(configured).origin) {
    throw new Error("The private object destination was not accepted.");
  }
  if (
    target.username ||
    target.password ||
    !new Set(["http:", "https:"]).has(target.protocol)
  ) {
    throw new Error("The private object destination was not accepted.");
  }
  return target;
}

export async function getAttachmentDownloadUrl(
  evidenceId: string,
  attachmentId: string,
): Promise<string> {
  const intent = parseAttachmentDownloadIntent(
    await (
      await query(
        careerVaultPaths.evidenceAttachmentDownload(evidenceId, attachmentId),
      )
    ).json(),
  );
  return validatedPrivateObjectUrl(intent.url).toString();
}

export function uploadAttachment(
  intent: AttachmentUploadIntent,
  file: File,
  onProgress: (percent: number | null) => void,
  signal: AbortSignal,
): Promise<void> {
  const target = validatedPrivateObjectUrl(intent.url);
  if (signal.aborted) {
    return Promise.reject(new Error("The attachment upload was cancelled."));
  }
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open(intent.method, target, true);
    request.timeout = 120_000;
    request.withCredentials = false;
    for (const [name, value] of Object.entries(intent.headers)) {
      request.setRequestHeader(name, value);
    }
    request.upload.onprogress = (event) =>
      onProgress(
        event.lengthComputable && event.total > 0
          ? Math.min(100, (event.loaded / event.total) * 100)
          : null,
      );
    request.onload = () =>
      request.status >= 200 && request.status < 300
        ? resolve()
        : reject(new Error("The attachment could not be transferred."));
    request.onerror = () =>
      reject(new Error("The attachment could not be transferred."));
    request.ontimeout = () =>
      reject(new Error("The attachment upload timed out."));
    request.onabort = () =>
      reject(new Error("The attachment upload was cancelled."));
    const abort = () => request.abort();
    signal.addEventListener("abort", abort, { once: true });
    request.onloadend = () => signal.removeEventListener("abort", abort);
    request.send(file);
  });
}

export async function finalizeAttachmentUpload(
  evidence: EvidenceItem,
  intent: AttachmentUploadIntent,
): Promise<EvidenceItem> {
  const response = await mutate(
    careerVaultPaths.evidenceAttachmentFinalize(evidence.id, intent.uploadId),
    {
      headers: headers(evidence.version, true),
      method: "POST",
    },
  );
  return parseEvidence(await response.json());
}

export async function deleteAttachment(
  evidence: EvidenceItem,
  attachmentId: string,
): Promise<EvidenceItem> {
  const response = await mutate(
    careerVaultPaths.evidenceAttachment(evidence.id, attachmentId),
    {
      headers: headers(evidence.version, true),
      method: "DELETE",
    },
  );
  return parseEvidence(await response.json());
}

export async function resolveEvidenceConflict(
  evidence: EvidenceItem,
  conflictId: string,
  resolution:
    "keep_both" | "mark_unsupported" | "prefer_current" | "prefer_related",
): Promise<EvidenceItem> {
  const response = await mutate(
    careerVaultPaths.evidenceConflictResolve(evidence.id, conflictId),
    {
      body: JSON.stringify({ resolution }),
      headers: headers(evidence.version, true),
      method: "POST",
    },
  );
  return parseEvidence(await response.json());
}

export async function getAchievements(): Promise<Page<Achievement>> {
  return parseAchievementPage(
    await (await query(careerVaultPaths.achievements)).json(),
  );
}

export async function createAchievement(
  input: AchievementInput,
): Promise<Achievement> {
  const response = await mutate(careerVaultPaths.achievements, {
    body: JSON.stringify(input),
    headers: headers(undefined, true),
    method: "POST",
  });
  return parseAchievement(await response.json());
}

export async function deleteAchievement(
  achievement: Achievement,
): Promise<void> {
  await mutate(careerVaultPaths.achievement(achievement.id), {
    headers: headers(achievement.version, true),
    method: "DELETE",
  });
}

export async function updateAchievement(
  achievement: Achievement,
  input: AchievementInput,
): Promise<Achievement> {
  const response = await mutate(careerVaultPaths.achievement(achievement.id), {
    body: JSON.stringify(input),
    headers: headers(achievement.version),
    method: "PATCH",
  });
  return parseAchievement(await response.json());
}

export async function convertAchievement(
  achievement: Achievement,
): Promise<Achievement> {
  const response = await mutate(
    careerVaultPaths.achievementConfirm(achievement.id),
    {
      headers: headers(achievement.version, true),
      method: "POST",
    },
  );
  return parseAchievement(await response.json());
}

export async function getReminderPreferences(): Promise<ReminderPreferences> {
  return parseReminderPreferences(
    await (await query(careerVaultPaths.achievementReminders)).json(),
  );
}

export async function updateReminderPreferences(
  current: ReminderPreferences,
  input: Omit<ReminderPreferences, "updatedAt" | "version">,
): Promise<ReminderPreferences> {
  const response = await mutate(careerVaultPaths.achievementReminders, {
    body: JSON.stringify(input),
    headers: headers(current.version),
    method: "PATCH",
  });
  return parseReminderPreferences(await response.json());
}

export { ApiRequestError };
