import { LoadingSkeleton } from "@careeros/ui";

export default function ResumeBuilderLoading() {
  return (
    <main
      className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8"
      id="main-content"
    >
      <LoadingSkeleton />
    </main>
  );
}
