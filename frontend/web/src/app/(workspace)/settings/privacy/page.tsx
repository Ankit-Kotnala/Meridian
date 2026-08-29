import type { Metadata } from "next";

import { PrivacySettings } from "@/modules/settings";

export const metadata: Metadata = { title: "Privacy settings" };

export default function PrivacySettingsPage() {
  return <PrivacySettings />;
}
