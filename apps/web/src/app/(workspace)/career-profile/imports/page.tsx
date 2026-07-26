import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { isResourceId, ProfileImportStartView } from "@/modules/career-vault";

export const metadata: Metadata = { title: "Import reviewed resume facts" };

export default async function ProfileImportStartPage({
  searchParams,
}: {
  searchParams: Promise<{
    documentId?: string;
    snapshotId?: string;
  }>;
}) {
  const { documentId, snapshotId } = await searchParams;
  if (
    documentId === undefined ||
    snapshotId === undefined ||
    !isResourceId(documentId) ||
    !isResourceId(snapshotId)
  ) {
    notFound();
  }
  return (
    <ProfileImportStartView documentId={documentId} snapshotId={snapshotId} />
  );
}
