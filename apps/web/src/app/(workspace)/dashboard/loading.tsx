import { LoadingSkeleton } from "@rezumi/ui";

export default function DashboardLoading() {
  return (
    <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8" id="main-content">
      <LoadingSkeleton />
    </main>
  );
}
