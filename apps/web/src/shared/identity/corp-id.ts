/**
 * Rezumi Corp ID.
 *
 * A stable, human-readable membership identifier derived from the account's own
 * UUID, so it needs no separate column while a dedicated immutable identifier is
 * still deferred (see ADR 0019). Because it is derived and truncated, it is a
 * display identifier only: it is not used to look an account up, and it must
 * never be presented as an employer credential, a background check, or a
 * third-party identity verification.
 */

/** Crockford base32: no I, L, O, or U, so a spoken ID is unambiguous. */
const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
const BODY_LENGTH = 10;

export type CorpIdTier = "evidenced" | "profiled" | "registered" | "unverified";

export type CorpIdChecks = {
  confirmedEvidence: number;
  emailVerified: boolean;
  experiences: number;
};

export type CorpIdStanding = {
  /** What this tier actually attests, in the user's own terms. */
  attests: string;
  label: string;
  /** The next check that would raise the tier, when one remains. */
  next?: string;
  tier: CorpIdTier;
};

/**
 * Render the Corp ID for an account UUID, or `null` when the identifier is not a
 * UUID we can derive from. Callers render nothing rather than inventing an ID.
 */
export function corpIdFor(userId: string): string | null {
  const hex = userId.replaceAll("-", "").toLowerCase();
  if (!/^[0-9a-f]{32}$/.test(hex)) return null;

  let value = BigInt(`0x${hex}`);
  const characters: string[] = [];
  while (characters.length < BODY_LENGTH) {
    characters.push(ALPHABET[Number(value % 32n)] ?? "0");
    value /= 32n;
  }
  const body = characters.reverse().join("");
  return `RZ-${body.slice(0, 5)}-${body.slice(5)}`;
}

/**
 * Standing is driven only by checks Rezumi performs itself. Nothing here
 * observes an employer, a hiring outcome, or a third party.
 */
export function corpIdStanding({
  confirmedEvidence,
  emailVerified,
  experiences,
}: CorpIdChecks): CorpIdStanding {
  if (!emailVerified) {
    return {
      attests: "This account has not confirmed its email address yet.",
      label: "Unverified",
      next: "Confirm your email address.",
      tier: "unverified",
    };
  }
  if (experiences < 1) {
    return {
      attests: "Meridian has confirmed control of this email address.",
      label: "Registered",
      next: "Add at least one role to your career record.",
      tier: "registered",
    };
  }
  if (confirmedEvidence < 1) {
    return {
      attests:
        "Meridian has confirmed this email address and holds a structured career record for this account.",
      label: "Profiled",
      next: "Confirm at least one evidence record.",
      tier: "profiled",
    };
  }
  return {
    attests:
      "Meridian has confirmed this email address, holds a structured career record, and that record has user-confirmed supporting evidence.",
    label: "Evidenced",
    tier: "evidenced",
  };
}

/** The scope limit that must accompany the identifier wherever it is shown. */
export const CORP_ID_DISCLAIMER =
  "A Corp ID records your standing with Meridian and the checks Meridian performed. It is not an employer credential, a background check, an identity verification by any third party, or a hiring signal.";
