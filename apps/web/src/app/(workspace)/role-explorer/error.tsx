"use client";

import { RoleExplorerRouteError } from "@/modules/role-explorer";

export default function Error({ reset }: { reset: () => void }) {
  return <RoleExplorerRouteError reset={reset} />;
}
