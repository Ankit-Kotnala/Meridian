import { readdir, readFile, stat } from "node:fs/promises";
import { relative, resolve, sep } from "node:path";

const root = resolve(import.meta.dirname, "..");
const sourceRoots = ["apps/web/src", "packages/ui/src"];
const sourceExtensions = new Set([".js", ".jsx", ".mjs", ".ts", ".tsx"]);
const forbiddenGenericSegments = new Set([
  "common",
  "helpers",
  "misc",
  "utils",
]);

function portable(path) {
  return path.split(sep).join("/");
}

function extension(path) {
  const match = /\.[^.\/]+$/.exec(path);
  return match?.[0] ?? "";
}

async function filesBelow(directory) {
  const absolute = resolve(root, directory);
  try {
    if (!(await stat(absolute)).isDirectory()) return [];
  } catch {
    return [];
  }

  const entries = await readdir(absolute, { withFileTypes: true });
  const nested = await Promise.all(
    entries.map((entry) => {
      const path = resolve(absolute, entry.name);
      return entry.isDirectory() ? filesBelow(relative(root, path)) : [path];
    }),
  );
  return nested.flat();
}

function importedSpecifiers(source) {
  const imports = [];
  const pattern = /(?:from\s*|import\s*\()\s*["']([^"']+)["']/g;
  for (const match of source.matchAll(pattern)) imports.push(match[1]);
  return imports;
}

function importViolations(path, specifier) {
  const violations = [];

  if (specifier.startsWith("@/components") || specifier.startsWith("@/lib")) {
    violations.push("WEB_GLOBAL_BUCKET");
  }
  if (
    path.startsWith("apps/web/src/modules/") &&
    specifier.startsWith("@/app")
  ) {
    violations.push("MODULE_TO_ROUTE");
  }
  if (
    path.startsWith("apps/web/src/shared/") &&
    (specifier.startsWith("@/app") || specifier.startsWith("@/modules"))
  ) {
    violations.push("SHARED_TO_PRODUCT");
  }
  if (
    path.startsWith("packages/ui/src/") &&
    (specifier === "next" ||
      specifier.startsWith("next/") ||
      specifier.startsWith("@/") ||
      specifier.startsWith("@rezumi/contracts") ||
      specifier.startsWith("@rezumi/test-fixtures"))
  ) {
    violations.push("UI_TO_APPLICATION");
  }

  return violations;
}

function verifyRuleProbes() {
  const probes = [
    [
      "apps/web/src/modules/example/view.tsx",
      "@/app/dashboard",
      "MODULE_TO_ROUTE",
    ],
    [
      "apps/web/src/shared/example.ts",
      "@/modules/dashboard",
      "SHARED_TO_PRODUCT",
    ],
    ["packages/ui/src/button.tsx", "next/link", "UI_TO_APPLICATION"],
    ["apps/web/src/app/page.tsx", "@/components/legacy", "WEB_GLOBAL_BUCKET"],
  ];
  for (const [path, specifier, expected] of probes) {
    if (!importViolations(path, specifier).includes(expected)) {
      throw new Error(`Boundary rule self-test failed for ${expected}.`);
    }
  }
}

verifyRuleProbes();

const violations = [];
for (const directory of ["apps/web/src/components", "apps/web/src/lib"]) {
  const legacyFiles = (await filesBelow(directory)).filter((path) =>
    sourceExtensions.has(extension(path)),
  );
  if (legacyFiles.length > 0) {
    violations.push(`${directory}: legacy global bucket must be migrated`);
  }
}

for (const sourceRoot of sourceRoots) {
  for (const absolute of await filesBelow(sourceRoot)) {
    const path = portable(relative(root, absolute));
    if (!sourceExtensions.has(extension(path))) continue;

    const segments = path.split("/");
    for (const segment of segments.slice(0, -1)) {
      if (forbiddenGenericSegments.has(segment)) {
        violations.push(`${path}: generic '${segment}' directory is forbidden`);
      }
    }

    const source = await readFile(absolute, "utf8");
    if (path.endsWith("/page.tsx") && source.split(/\r?\n/).length > 100) {
      violations.push(
        `${path}: route file exceeds the 100-line delivery-layer limit`,
      );
    }

    for (const specifier of importedSpecifiers(source)) {
      for (const code of importViolations(path, specifier)) {
        violations.push(`${path}: ${code} import '${specifier}'`);
      }
    }
  }
}

const apiRoot = "apps/api/src/rezumi_api";
for (const absolute of await filesBelow(apiRoot)) {
  const path = portable(relative(root, absolute));
  const relativeApiPath = path.slice(apiRoot.length + 1);
  if (
    !relativeApiPath.includes("/") &&
    /_(dependencies|presenters|routes|schemas)\.py$/.test(relativeApiPath)
  ) {
    violations.push(
      `${path}: feature delivery adapters belong in modules/<bounded_context>`,
    );
  }
}

const requiredWorkerTaskModules = [
  "career_analytics.py",
  "career_record.py",
  "health.py",
  "networking.py",
  "resume_builder.py",
  "resume_health.py",
];
for (const filename of requiredWorkerTaskModules) {
  const path = resolve(root, "apps/worker/src/rezumi_worker/tasks", filename);
  try {
    if (!(await stat(path)).isFile()) throw new Error("not a file");
  } catch {
    violations.push(
      `apps/worker/src/rezumi_worker/tasks/${filename}: required bounded task module is missing`,
    );
  }
}
try {
  if (
    (
      await stat(resolve(root, "apps/worker/src/rezumi_worker/tasks.py"))
    ).isFile()
  ) {
    violations.push(
      "apps/worker/src/rezumi_worker/tasks.py: monolithic task module is forbidden",
    );
  }
} catch {
  // The expected normalized state has no flat task module.
}

if (violations.length > 0) {
  console.error(
    "Repository boundary violations:\n" +
      violations.map((item) => `- ${item}`).join("\n"),
  );
  process.exit(1);
}

console.log("Repository boundary checks passed.");
