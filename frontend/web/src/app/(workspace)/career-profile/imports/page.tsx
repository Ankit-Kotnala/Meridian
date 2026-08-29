import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { isResourceId, ProfileImportStartView } from "@/modules/career-vault";

export const metadata: Metadata = { title: "Import reviewed resume facts" };

/**
 * Both a specific reviewed snapshot and the standing list of proposals resolve
 * here. Without the snapshot parameters this page used to 404, which is exactly
 * where the workspace home sends someone to accept pending resume facts.
 */
export default async function ProfileImportStartPage({
  searchParams,
}: {
  searchParams: Promise<{
    documentId?: string;
    snapshotId?: string;
  }>;
}) {
  const { documentId, snapshotId } = await searchParams;
  if (documentId === undefined && snapshotId === undefined) {
    return <ProfileImportStartView />;
  }
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
