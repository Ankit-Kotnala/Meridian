/** Skeleton that mirrors the workspace home layout so the page does not jump. */
export function DashboardLoading() {
  return (
    <main
      aria-busy="true"
      aria-live="polite"
      className="workspace-page space-y-8"
      id="main-content"
      role="status"
    >
      <span className="sr-only">Loading your workspace</span>

      <div className="workspace-hero grid animate-pulse gap-7 px-5 py-6 sm:px-8 sm:py-8 lg:grid-cols-[minmax(0,1.15fr)_minmax(19rem,0.85fr)]">
        <div className="space-y-3">
          <div className="h-3 w-28 rounded bg-surface-inset" />
          <div className="h-8 w-3/4 rounded-md bg-surface-inset" />
          <div className="h-3 w-full max-w-md rounded bg-surface-subtle" />
          <div className="h-3 w-2/3 max-w-sm rounded bg-surface-subtle" />
        </div>
        <div className="h-44 rounded-[var(--radius-card)] border border-line bg-surface" />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <div
            className="h-36 animate-pulse rounded-[var(--radius-card)] border border-line bg-surface"
            key={index}
          />
        ))}
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <div className="h-64 animate-pulse rounded-[var(--radius-card)] border border-line bg-surface" />
        <div className="h-64 animate-pulse rounded-[var(--radius-card)] border border-line bg-surface" />
      </div>

      <div className="h-52 animate-pulse rounded-[var(--radius-card)] border border-line bg-surface" />
    </main>
  );
}
