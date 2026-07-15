import type { Metadata } from "next";

import { ProfileSettings } from "@/modules/settings";

export const metadata: Metadata = { title: "Profile settings" };

export default function SettingsPage() {
  return <ProfileSettings />;
}
