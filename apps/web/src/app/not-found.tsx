import Link from "next/link";

import { EmptyState } from "@/components/ui/async-state";
import { buttonStyles } from "@/components/ui/button";
import { cn } from "@/lib/cn";

export default function NotFound() {
  return (
    <main className="site-container py-20" id="main-content">
      <EmptyState
        action={
          <Link
            className={cn(buttonStyles.base, buttonStyles.primary)}
            href="/"
          >
            Return home
          </Link>
        }
        description="The page may have moved, or it is not part of this product preview."
        title="Page not found"
      />
    </main>
  );
}
