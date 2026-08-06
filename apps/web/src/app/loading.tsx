import { LoadingSkeleton } from "@rezumi/ui";

export default function Loading() {
  return (
    <main className="site-container py-20" id="main-content">
      <LoadingSkeleton />
    </main>
  );
}
