import type { MetadataRoute } from "next";

import { publicPages } from "@/modules/marketing";

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
  return [
    { url: baseUrl, changeFrequency: "weekly", priority: 1 },
    ...Object.keys(publicPages).map((slug) => ({
      url: `${baseUrl}/${slug}`,
      changeFrequency: "monthly" as const,
      priority: 0.6,
    })),
  ];
}
