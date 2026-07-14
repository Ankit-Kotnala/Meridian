import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CanonicalReviewView, isResourceId } from "@/modules/resume-health";

export const metadata: Metadata = { title: "Review parsed resume" };

export default async function AccountReviewPage({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const { documentId } = await params;
  if (!isResourceId(documentId)) notFound();
  return <CanonicalReviewView access="account" documentId={documentId} />;
}
