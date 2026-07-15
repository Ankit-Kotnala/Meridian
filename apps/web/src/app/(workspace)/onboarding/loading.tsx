import { LoadingSkeleton } from "@careeros/ui";

export default function OnboardingLoading() {
  return (
    <main className="mx-auto max-w-5xl p-4 sm:p-6 lg:p-8" id="main-content">
      <LoadingSkeleton />
    </main>
  );
}
