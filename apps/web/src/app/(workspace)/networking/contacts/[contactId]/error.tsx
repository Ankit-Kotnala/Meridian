"use client";

import { ContactRouteError } from "@/modules/networking";

export default function Error({ reset }: { reset: () => void }) {
  return <ContactRouteError reset={reset} />;
}
