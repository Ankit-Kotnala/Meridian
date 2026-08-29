import { LoadingSkeleton } from "@rezumi/ui";

export default function DashboardDemoLoading() {
  return (
    <main className="mx-auto max-w-[98rem] p-6" id="main-content">
      <LoadingSkeleton />
    </main>
  );
}
