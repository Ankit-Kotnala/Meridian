import type { Metadata } from "next";

import { ResetPasswordView } from "@/modules/auth";

export const metadata: Metadata = { title: "Reset password" };

export default function ResetPasswordPage() {
  return <ResetPasswordView />;
}
