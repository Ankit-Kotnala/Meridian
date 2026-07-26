"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@careeros/ui";

import { WorkspaceSidebar } from "./workspace-sidebar";
import { WorkspaceTopBar } from "./workspace-top-bar";

export type WorkspaceViewer = {
  displayName: string;
  email: string;
};

export function WorkspaceShell({
  accountActions,
  children,
  viewer,
}: {
  accountActions: ReactNode;
  children: ReactNode;
  viewer: WorkspaceViewer;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (mobileOpen && !dialog.open) dialog.showModal();
    if (!mobileOpen && dialog.open) dialog.close();
  }, [mobileOpen]);

  function closeMobileNavigation({ restoreFocus = true } = {}) {
    setMobileOpen(false);
    if (restoreFocus) queueMicrotask(() => menuButtonRef.current?.focus());
  }

  return (
    <div className="min-h-screen bg-background">
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 hidden transition-[width] duration-200 motion-reduce:transition-none lg:block",
          collapsed ? "w-[4.25rem]" : "w-[var(--sidebar-width)]",
        )}
      >
        <WorkspaceSidebar
          collapsed={collapsed}
          onCollapse={() => setCollapsed((value) => !value)}
        />
      </aside>

      <dialog
        aria-label="Application navigation"
        className="m-0 h-dvh max-h-none w-[min(20rem,90vw)] max-w-none bg-transparent p-0 backdrop:bg-foreground/45 lg:hidden"
        onCancel={(event) => {
          event.preventDefault();
          closeMobileNavigation();
        }}
        onClose={() => setMobileOpen(false)}
        ref={dialogRef}
      >
        <WorkspaceSidebar
          onClose={() => closeMobileNavigation()}
          onNavigate={() => closeMobileNavigation({ restoreFocus: false })}
        />
      </dialog>

      <div
        className={cn(
          "transition-[padding] duration-200 motion-reduce:transition-none",
          collapsed ? "lg:pl-[4.25rem]" : "lg:pl-[var(--sidebar-width)]",
        )}
      >
        <WorkspaceTopBar
          accountActions={accountActions}
          menuButtonRef={menuButtonRef}
          onOpenMenu={() => setMobileOpen(true)}
          viewer={viewer}
        />
        {children}
      </div>
    </div>
  );
}
