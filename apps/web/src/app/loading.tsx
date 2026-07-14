import { LoadingSkeleton } from "@/components/ui/async-state";

export default function Loading() {
  return (
    <main className="site-container py-20" id="main-content">
      <LoadingSkeleton />
    </main>
  );
}
