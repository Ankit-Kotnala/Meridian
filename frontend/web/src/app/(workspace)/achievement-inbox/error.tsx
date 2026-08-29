"use client";

import { CareerVaultRouteError } from "@/modules/career-vault";

export default function AchievementInboxError({
  reset,
}: {
  reset: () => void;
}) {
  return (
    <CareerVaultRouteError
      description="Achievement Inbox could not be displayed. No draft was changed."
      reset={reset}
      title="Achievement Inbox unavailable"
    />
  );
}
