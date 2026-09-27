"use client";

import { m } from "motion/react";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@rezumi/ui";
import { ProductMotionProvider } from "@/shared/motion/product-motion-provider";
import { InterviewPrepWorkspaceMetricsProvider } from "@/shared/workspace/interview-prep-workspace-metrics";

import { WorkspaceSectionNav } from "./workspace-section-nav";
import { WorkspaceSidebar } from "./workspace-sidebar";
import { WorkspaceTopBar } from "./workspace-top-bar";

export type WorkspaceViewer = {
  displayName: string;
  email: string;
  id: string;
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
  const pathname = usePathname();

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
    <ProductMotionProvider>
      <InterviewPrepWorkspaceMetricsProvider>
        <div
          className={cn(
            "min-h-screen bg-background xl:grid xl:transition-[grid-template-columns] xl:duration-200 xl:motion-reduce:transition-none",
            collapsed
              ? "xl:grid-cols-[4.25rem_minmax(0,1fr)]"
              : "xl:grid-cols-[var(--sidebar-width)_minmax(0,1fr)]",
          )}
        >
          <aside
            className={cn(
              "relative z-20 hidden h-dvh border-r transition-[width] duration-200 motion-reduce:transition-none xl:sticky xl:top-0 xl:block",
              collapsed ? "w-[4.25rem]" : "w-[var(--sidebar-width)]",
            )}
            style={{ borderRightColor: "rgb(255 255 255 / 0.1)" }}
          >
            <WorkspaceSidebar
              collapsed={collapsed}
              onCollapse={() => setCollapsed((value) => !value)}
            />
          </aside>

          <dialog
            aria-label="Application navigation"
            className="m-0 h-dvh max-h-none w-[min(20rem,90vw)] max-w-none bg-transparent p-0 backdrop:bg-foreground/45 xl:hidden"
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

          <div className="workspace-content min-w-0">
            <WorkspaceTopBar
              accountActions={accountActions}
              menuButtonRef={menuButtonRef}
              onOpenMenu={() => setMobileOpen(true)}
              viewer={viewer}
            />
            <WorkspaceSectionNav />
            <m.div
              animate={{ opacity: 1, y: 0 }}
              className="workspace-canvas min-w-0"
              data-route-frame
              initial={{ opacity: 0, y: 8 }}
              key={pathname}
              transition={{
                duration: 0.28,
                ease: [0.22, 1, 0.36, 1],
              }}
            >
              {children}
            </m.div>
          </div>
        </div>
      </InterviewPrepWorkspaceMetricsProvider>
    </ProductMotionProvider>
  );
}
