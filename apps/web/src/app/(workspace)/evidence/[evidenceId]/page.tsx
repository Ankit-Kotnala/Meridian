import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { EvidenceDetailView, isResourceId } from "@/modules/career-vault";

export const metadata: Metadata = { title: "Evidence details" };

export default async function EvidenceDetailPage({
  params,
}: {
  params: Promise<{ evidenceId: string }>;
}) {
  const { evidenceId } = await params;
  if (!isResourceId(evidenceId)) notFound();
  return <EvidenceDetailView evidenceId={evidenceId} />;
}
