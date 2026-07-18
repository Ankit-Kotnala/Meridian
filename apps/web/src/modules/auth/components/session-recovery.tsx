"use client";

import { LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { refreshSession } from "@/shared/api/browser-request";

function currentReturnTo(): string {
  const value = `${window.location.pathname}${window.location.search}`;
  return value.startsWith("/") && !value.startsWith("//")
    ? value
    : "/dashboard";
}

export function SessionRecovery() {
  const router = useRouter();

  useEffect(() => {
    let active = true;
    void refreshSession()
      .then(() => {
        if (active) window.location.reload();
      })
      .catch(() => {
        if (active) {
          router.replace(
            `/login?returnTo=${encodeURIComponent(currentReturnTo())}`,
          );
        }
      });
    return () => {
      active = false;
    };
  }, [router]);

  return (
    <main
      className="grid min-h-screen place-items-center bg-background px-4"
      id="main-content"
    >
      <div className="surface-card max-w-md rounded-2xl p-8 text-center">
        <LoaderCircle
          aria-hidden="true"
          className="mx-auto size-7 animate-spin text-primary motion-reduce:animate-none"
        />
        <h1 className="mt-4 text-xl font-black text-foreground">
          Restoring your secure session
        </h1>
        <p aria-live="polite" className="mt-2 text-sm leading-6 text-muted">
          CareerOS is checking your signed-in session before showing private
          account information.
        </p>
      </div>
    </main>
  );
}
