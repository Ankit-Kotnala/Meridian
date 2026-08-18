import { corpIdStanding, type CorpIdChecks } from "./corp-id";

/**
 * Rezumi Corp ID credential artifact.
 *
 * The card is a fixed artifact rather than a themed surface: it must rasterize
 * to the same image regardless of the viewer's theme, so its palette is
 * self-contained and it carries no theme tokens. Everything drawn here is
 * either the holder's own data or a statement of what Rezumi checked.
 */

export const CREDENTIAL_WIDTH = 1012;
export const CREDENTIAL_HEIGHT = 638;

export type CredentialDetails = {
  checks: CorpIdChecks;
  corpId: string;
  displayName: string;
  /** Rendered as the generation date, never as an account-opening date. */
  generatedOn: string;
};

function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

/** Truncate a long name so it cannot overflow the card artwork. */
function fit(value: string, max: number): string {
  const trimmed = value.trim();
  return trimmed.length <= max ? trimmed : `${trimmed.slice(0, max - 1)}…`;
}

/**
 * Deterministic decorative bars derived from the Corp ID.
 *
 * This is artwork, not an encoding: it carries no recoverable data and must
 * never be presented as a scannable or verifiable feature.
 */
function guilloche(corpId: string): string {
  const seed = [...corpId].reduce(
    (total, character) => total + character.codePointAt(0)!,
    0,
  );
  return Array.from({ length: 34 }, (_, index) => {
    const height = 6 + ((seed * (index + 3)) % 27);
    const x = 604 + index * 11;
    return `<rect x="${x}" y="${520 - height}" width="5" height="${height}" rx="2" fill="#7fd6b4" opacity="${0.18 + ((seed + index) % 5) * 0.06}"/>`;
  }).join("");
}

export function credentialSvg({
  checks,
  corpId,
  displayName,
  generatedOn,
}: CredentialDetails): string {
  const standing = corpIdStanding(checks);
  // Case-fold before escaping: uppercasing after would corrupt entities to `&LT;`.
  const name = escapeXml(fit(displayName, 30).toUpperCase());
  const id = escapeXml(corpId);
  const tier = escapeXml(standing.label.toUpperCase());

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${CREDENTIAL_WIDTH}" height="${CREDENTIAL_HEIGHT}" viewBox="0 0 ${CREDENTIAL_WIDTH} ${CREDENTIAL_HEIGHT}" role="img" aria-label="Rezumi Corp ID credential for ${escapeXml(fit(displayName, 30))}">
  <defs>
    <linearGradient id="rz-bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0f2c22"/>
      <stop offset="0.55" stop-color="#123528"/>
      <stop offset="1" stop-color="#0a1f18"/>
    </linearGradient>
    <linearGradient id="rz-rail" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#2f9c74"/>
      <stop offset="0.5" stop-color="#35b6b0"/>
      <stop offset="1" stop-color="#8fe0c0"/>
    </linearGradient>
    <radialGradient id="rz-glow" cx="0.86" cy="0.1" r="0.6">
      <stop offset="0" stop-color="#35b6b0" stop-opacity="0.34"/>
      <stop offset="1" stop-color="#35b6b0" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect width="${CREDENTIAL_WIDTH}" height="${CREDENTIAL_HEIGHT}" rx="34" fill="url(#rz-bg)"/>
  <rect width="${CREDENTIAL_WIDTH}" height="${CREDENTIAL_HEIGHT}" rx="34" fill="url(#rz-glow)"/>
  <rect x="1.5" y="1.5" width="${CREDENTIAL_WIDTH - 3}" height="${CREDENTIAL_HEIGHT - 3}" rx="32.5" fill="none" stroke="#5fcfa6" stroke-opacity="0.34" stroke-width="3"/>
  <rect x="0" y="0" width="${CREDENTIAL_WIDTH}" height="9" rx="4" fill="url(#rz-rail)"/>

  <g transform="translate(58 62)">
    <rect width="52" height="52" rx="15" fill="url(#rz-rail)"/>
    <path d="M15 34 L26 15 L37 34 Z" fill="#0f2c22"/>
    <text x="70" y="22" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="21" font-weight="700" fill="#eafaf2" letter-spacing="0.5">Rezumi</text>
    <text x="70" y="44" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13" font-weight="600" fill="#8fd9bd" letter-spacing="2.4">CAREER CREDENTIAL</text>
  </g>

  <g transform="translate(58 210)">
    <text y="0" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13" font-weight="700" fill="#7cc7a8" letter-spacing="2.6">HOLDER</text>
    <text y="46" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="38" font-weight="700" fill="#ffffff" letter-spacing="0.4">${name}</text>
  </g>

  <g transform="translate(58 330)">
    <text y="0" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13" font-weight="700" fill="#7cc7a8" letter-spacing="2.6">CORP ID</text>
    <text y="54" font-family="Consolas, Menlo, monospace" font-size="46" font-weight="700" fill="#8fe0c0" letter-spacing="3">${id}</text>
  </g>

  <g transform="translate(58 436)">
    <rect width="212" height="42" rx="21" fill="#7fd6b4" fill-opacity="0.16" stroke="#7fd6b4" stroke-opacity="0.5"/>
    <text x="24" y="28" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="15" font-weight="700" fill="#b6ecd5" letter-spacing="1.8">${tier}</text>
    <text x="240" y="19" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12" font-weight="600" fill="#6fb79b" letter-spacing="1.6">GENERATED</text>
    <text x="240" y="37" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="14" font-weight="700" fill="#d6f4e6">${escapeXml(generatedOn)}</text>
  </g>

  ${guilloche(corpId)}

  <text x="58" y="580" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13" font-weight="600" fill="#9fd8c1">${escapeXml(standing.attests)}</text>
  <text x="58" y="606" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12" fill="#6aa891">Not an employer credential, a background check, a third-party identity verification, or a hiring signal.</text>
</svg>`;
}

export function credentialFileName(corpId: string, extension: string): string {
  return `rezumi-corp-id-${corpId.toLowerCase()}.${extension}`;
}
