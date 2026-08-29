import {
  acceptProfileImportProposal,
  createProfileImportProposals,
  listProfileImportProposals,
} from "../api/career-vault-api";
import { planAutoImport } from "./eligibility";

export type AutoImportResult = {
  applied: number;
  held: number;
  questions: number;
};

export type AutoImportProgress = {
  done: number;
  total: number;
};

/**
 * Derive import proposals from a reviewed snapshot, then apply every
 * unambiguous one. Safe to call repeatedly: proposal creation is idempotent
 * on (snapshot, semantic entity).
 */
export async function runAutoImport(
  documentId?: string,
  snapshotId?: string,
  onProgress?: (progress: AutoImportProgress) => void,
): Promise<AutoImportResult> {
  let questions = 0;
  let appliedFromCreate = 0;
  if (documentId !== undefined && snapshotId !== undefined) {
    try {
      const batch = await createProfileImportProposals(documentId, snapshotId);
      questions = batch.questions.length;
      appliedFromCreate = batch.appliedCount ?? 0;
    } catch {
      questions = 0;
    }
  }

  const { apply, hold } = planAutoImport(await listProfileImportProposals());
  let applied = appliedFromCreate;
  onProgress?.({ done: 0, total: apply.length });
  for (const proposal of apply) {
    await acceptProfileImportProposal(proposal, {}, crypto.randomUUID());
    applied += 1;
    onProgress?.({ done: applied, total: apply.length });
  }

  return { applied, held: hold.length, questions };
}
