"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@rezumi/ui";

import { authErrorMessage, logout } from "../api/auth-api";

export function LogoutButton() {
  const router = useRouter();
  const [failure, setFailure] = useState<string>();
  const [loading, setLoading] = useState(false);

  return (
    <div>
      {failure && (
        <p
          className="px-3 py-2 text-xs font-semibold leading-5 text-danger"
          role="alert"
        >
          {failure}
        </p>
      )}
      <Button
        className="w-full justify-start"
        loading={loading}
        loadingLabel="Signing out…"
        onClick={async () => {
          setLoading(true);
          setFailure(undefined);
          try {
            await logout();
            router.replace("/login");
            router.refresh();
          } catch (error) {
            setFailure(
              authErrorMessage(error, "We couldn’t sign you out. Try again."),
            );
          } finally {
            setLoading(false);
          }
        }}
        variant="ghost"
      >
        <LogOut aria-hidden="true" className="size-4" /> Sign out
      </Button>
    </div>
  );
}
