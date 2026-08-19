import type { ProfileImportProposal } from "../api/types";

/**
 * Zero-touch career-record import.
 *
 * Every field in an import proposal has already passed through typed resume
 * review, where a person confirmed, corrected, or typed it. Asking that person
 * to accept the same value a second time is redundant double-confirmation, so
 * proposals that are unambiguous are applied without another prompt.
 *
 * What still stops for review is deliberately narrow: a conflict with an
 * existing record, a value the parser could not trace back to the file, low
 * parser confidence, or a source snapshot that is no longer available. Those are
 * the cases where a silent write could put a claim in the record that the person
 * did not actually settle.
 */

/** Parser confidence required for a value that was not typed by the user. */
export const AUTO_IMPORT_MIN_CONFIDENCE = 0.9;

export type AutoImportHold =
  "conflict" | "lowConfidence" | "sourceUnavailable" | "untraceable";

/** Why a proposal is being held back, or `null` when it can be applied. */
export function autoImportHold(
  proposal: ProfileImportProposal,
): AutoImportHold | null {
  if (proposal.status !== "pending") return null;
  if (!proposal.sourceAvailable) return "sourceUnavailable";
  if (proposal.changes.length === 0) return "untraceable";

  for (const change of proposal.changes) {
    if (change.conflict !== null) return "conflict";
    // Values settled during typed resume review do not need a second gate.
    if (
      change.reviewState === "user_added" ||
      change.reviewState === "confirmed" ||
      change.reviewState === "corrected"
    ) {
      continue;
    }
    if (change.source.spans.length === 0) return "untraceable";
    const confidence = change.source.confidence;
    if (confidence !== null && confidence < AUTO_IMPORT_MIN_CONFIDENCE) {
      return "lowConfidence";
    }
  }
  return null;
}

export function isAutoApplicable(proposal: ProfileImportProposal): boolean {
  return proposal.status === "pending" && autoImportHold(proposal) === null;
}

export type AutoImportPlan = {
  apply: readonly ProfileImportProposal[];
  hold: readonly { hold: AutoImportHold; proposal: ProfileImportProposal }[];
};

/** Split pending proposals into what applies silently and what needs a person. */
export function planAutoImport(
  proposals: readonly ProfileImportProposal[],
): AutoImportPlan {
  const apply: ProfileImportProposal[] = [];
  const hold: { hold: AutoImportHold; proposal: ProfileImportProposal }[] = [];

  for (const proposal of proposals) {
    if (proposal.status !== "pending") continue;
    const held = autoImportHold(proposal);
    if (held === null) apply.push(proposal);
    else hold.push({ hold: held, proposal });
  }
  return { apply, hold };
}

const HOLD_REASONS: Record<AutoImportHold, string> = {
  conflict: "conflicts with a record you already have",
  lowConfidence: "the parser was not confident enough to apply it silently",
  sourceUnavailable: "the reviewed source snapshot is no longer available",
  untraceable: "it could not be traced back to a location in your file",
};

export function autoImportHoldReason(hold: AutoImportHold): string {
  return HOLD_REASONS[hold];
}
