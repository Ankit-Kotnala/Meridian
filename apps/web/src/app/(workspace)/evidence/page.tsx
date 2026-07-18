import type { Metadata } from "next";

import { EvidenceVaultView } from "@/modules/career-vault";

export const metadata: Metadata = { title: "Evidence Vault" };

export default function EvidenceVaultPage() {
  return <EvidenceVaultView />;
}
