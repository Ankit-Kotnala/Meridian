import { cn } from "@rezumi/ui";

export function workspaceSectionNavListClassName(): string {
  return "mx-auto flex w-full max-w-[var(--content-wide)] gap-6 overflow-x-auto px-[var(--space-page-inline)] scroll-strip";
}

export function workspaceSectionNavItemClassName(active: boolean): string {
  return cn(
    "-mb-px flex min-h-11 shrink-0 items-center border-b-2 text-[0.8125rem] font-semibold transition-colors",
    active
      ? "border-info text-info"
      : "border-transparent text-foreground hover:border-line-strong hover:text-muted-strong",
  );
}
