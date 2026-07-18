import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { isResourceId, ProfileImportReviewView } from "@/modules/career-vault";

export const metadata: Metadata = { title: "Review career profile import" };

export default async function ProfileImportReviewPage({
  params,
}: {
  params: Promise<{ proposalId: string }>;
}) {
  const { proposalId } = await params;
  if (!isResourceId(proposalId)) notFound();
  return <ProfileImportReviewView proposalId={proposalId} />;
}
