import type { Metadata } from "next";

import { AchievementInboxView } from "@/modules/career-vault";

export const metadata: Metadata = { title: "Achievement Inbox" };

export default function AchievementInboxPage() {
  return <AchievementInboxView />;
}
