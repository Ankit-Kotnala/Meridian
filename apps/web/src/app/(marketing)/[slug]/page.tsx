import type { Metadata } from "next";
import { notFound } from "next/navigation";

import {
  isPublicPageSlug,
  PublicInformationPage,
  publicPages,
} from "@/modules/marketing";

export const dynamicParams = false;

export function generateStaticParams() {
  return Object.keys(publicPages).map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  if (!isPublicPageSlug(slug)) return {};
  return {
    title: publicPages[slug].title,
    description: publicPages[slug].intro,
  };
}

export default async function PublicInformationRoute({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  if (!isPublicPageSlug(slug)) notFound();
  return <PublicInformationPage page={publicPages[slug]} />;
}
