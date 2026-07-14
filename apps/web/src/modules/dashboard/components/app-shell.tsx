"use client";

import { useEffect, useRef, useState } from "react";

import { cn } from "@careeros/ui";

import { Sidebar } from "@/modules/dashboard/components/sidebar";
import { TopBar } from "@/modules/dashboard/components/top-bar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (mobileOpen && !dialog.open) dialog.showModal();
    if (!mobileOpen && dialog.open) dialog.close();
  }, [mobileOpen]);

  return (
    <div className="min-h-screen bg-background">
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 hidden transition-[width] duration-200 lg:block",
          collapsed ? "w-[4.5rem]" : "w-[14.5rem]",
        )}
      >
        <Sidebar
          collapsed={collapsed}
          onCollapse={() => setCollapsed((value) => !value)}
        />
      </aside>
      <dialog
        aria-label="Application navigation"
        className="m-0 h-dvh max-h-none w-[min(19rem,86vw)] max-w-none bg-transparent p-0 backdrop:bg-navy/60 lg:hidden"
        onClose={() => setMobileOpen(false)}
        ref={dialogRef}
      >
        <Sidebar onNavigate={() => setMobileOpen(false)} />
      </dialog>
      <div
        className={cn(
          "transition-[padding] duration-200",
          collapsed ? "lg:pl-[4.5rem]" : "lg:pl-[14.5rem]",
        )}
      >
        <TopBar onOpenMenu={() => setMobileOpen(true)} />
        {children}
      </div>
    </div>
  );
}
