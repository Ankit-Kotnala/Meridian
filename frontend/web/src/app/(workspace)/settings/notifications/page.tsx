import type { Metadata } from "next";

import { NotificationSettings } from "@/modules/settings";

export const metadata: Metadata = { title: "Notification settings" };

export default function NotificationSettingsPage() {
  return <NotificationSettings />;
}
