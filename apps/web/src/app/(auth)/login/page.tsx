import type { Metadata } from "next";
import { Suspense } from "react";

import { LoginView } from "@/modules/auth";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <Suspense
      fallback={<p className="p-8 text-sm text-muted">Preparing sign in…</p>}
    >
      <LoginView />
    </Suspense>
  );
}
