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
  const [mobileOpenPath, setMobileOpenPath] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const pathname = usePathname();
  const mobileOpen = mobileOpenPath === pathname;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (mobileOpen && !dialog.open) dialog.showModal();
    if (!mobileOpen && dialog.open) dialog.close();
  }, [mobileOpen]);

  useEffect(() => {
    // A native modal remains in the top layer even if its contents become
    // hidden at the desktop breakpoint. Close it as the layout changes so it
    // can never leave an invisible backdrop over the workspace.
    if (typeof window.matchMedia !== "function") return;
    const desktopViewport = window.matchMedia("(min-width: 1280px)");
    const closeAtDesktopBreakpoint = () => {
      if (desktopViewport.matches) setMobileOpenPath(null);
    };
    closeAtDesktopBreakpoint();
    desktopViewport.addEventListener("change", closeAtDesktopBreakpoint);
    return () => {
      desktopViewport.removeEventListener("change", closeAtDesktopBreakpoint);
    };
  }, []);

  function closeMobileNavigation({ restoreFocus = true } = {}) {
    setMobileOpenPath(null);
    if (restoreFocus) queueMicrotask(() => menuButtonRef.current?.focus());
  }

  return (
    <ProductMotionProvider>
      <InterviewPrepWorkspaceMetricsProvider>
        <div
          className={cn(
            "min-h-screen overflow-x-clip bg-background xl:grid xl:transition-[grid-template-columns] xl:duration-300 xl:ease-[var(--ease-emphasized)] xl:motion-reduce:transition-none",
            collapsed
              ? "xl:grid-cols-[4.25rem_minmax(0,1fr)]"
              : "xl:grid-cols-[var(--sidebar-width)_minmax(0,1fr)]",
          )}
        >
          <aside
            className={cn(
              "relative z-20 hidden h-dvh min-w-0 border-r xl:sticky xl:top-0 xl:block",
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
            className="workspace-mobile-nav fixed inset-y-0 left-0 z-50 m-0 box-border h-dvh max-h-none w-[min(20rem,90vw)] max-w-none overflow-hidden border-0 bg-navy p-0 text-white shadow-[var(--shadow-lg)] backdrop:bg-foreground/45 xl:hidden"
            onCancel={(event) => {
              event.preventDefault();
              closeMobileNavigation();
            }}
            onClose={() => setMobileOpenPath(null)}
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
              onOpenMenu={() => setMobileOpenPath(pathname)}
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
