import type { Metadata } from "next";

import { VerifyEmailView } from "@/modules/auth";

export const metadata: Metadata = { title: "Verify email" };

export default function VerifyEmailPage() {
  return <VerifyEmailView />;
}
