import { LoadingSkeleton } from "@careeros/ui";

export default function DashboardLoading() {
  return (
    <main className="mx-auto max-w-[98rem] p-6" id="main-content">
      <LoadingSkeleton />
    </main>
  );
}
