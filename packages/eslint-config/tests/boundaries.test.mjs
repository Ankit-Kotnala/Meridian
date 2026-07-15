import assert from "node:assert/strict";
import test from "node:test";

import { boundaryViolation } from "../check-web-boundaries.mjs";

test("rejects a feature module importing a Next route", () => {
  assert.match(
    boundaryViolation(
      "apps/web/src/modules/dashboard/views/dashboard-page.tsx",
      "@/app/dashboard/actions",
    ),
    /must not import Next route files/,
  );
});

test("rejects a feature module deep-importing another module", () => {
  assert.match(
    boundaryViolation(
      "apps/web/src/modules/dashboard/views/dashboard-page.tsx",
      "@/modules/marketing/components/site-header",
    ),
    /must not deep-import another feature module/,
  );
  assert.match(
    boundaryViolation(
      "apps/web/src/modules/dashboard/views/dashboard-page.tsx",
      "../../marketing/components/site-header",
    ),
    /must not deep-import another feature module/,
  );
});

test("allows a module to use its own components and shared code", () => {
  assert.equal(
    boundaryViolation(
      "apps/web/src/modules/dashboard/views/dashboard-page.tsx",
      "@/modules/dashboard/components/app-shell",
    ),
    undefined,
  );
  assert.equal(
    boundaryViolation(
      "apps/web/src/modules/dashboard/views/dashboard-page.tsx",
      "@/shared/components/careeros-logo",
    ),
    undefined,
  );
});

test("rejects shared code importing a feature", () => {
  assert.match(
    boundaryViolation(
      "apps/web/src/shared/components/careeros-logo.tsx",
      "@/modules/marketing",
    ),
    /shared web code must not import routes or feature modules/,
  );
});
