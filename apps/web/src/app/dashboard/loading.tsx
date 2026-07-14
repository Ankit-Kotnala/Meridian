import { LoadingSkeleton } from "@/components/ui/async-state";

export default function DashboardLoading() {
  return (
    <main className="mx-auto max-w-[98rem] p-6" id="main-content">
      <LoadingSkeleton />
    </main>
  );
}
