import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE_FILE = /\.[cm]?[jt]sx?$/;
const IMPORT_SOURCE =
  /(?:import|export)\s+(?:[\s\S]*?\s+from\s+)?["']([^"']+)["']/g;

function normalize(value) {
  return value.replaceAll("\\", "/");
}

function moduleName(importer) {
  return normalize(importer).match(/(?:^|\/)src\/modules\/([^/]+)\//)?.[1];
}

function importedModuleName(importer, source) {
  const aliasOwner = source.match(/^@\/modules\/([^/]+)(?:\/|$)/)?.[1];
  if (aliasOwner) return aliasOwner;
  if (!source.startsWith(".")) return undefined;
  const resolved = normalize(path.resolve(path.dirname(importer), source));
  return moduleName(`${resolved}/`);
}

export function boundaryViolation(importer, source) {
  const normalizedImporter = normalize(importer);
  const owner = moduleName(normalizedImporter);

  if (owner && (source === "@/app" || source.startsWith("@/app/"))) {
    return "feature modules must not import Next route files";
  }

  const importedModule = importedModuleName(importer, source);
  if (owner && importedModule && importedModule !== owner) {
    return "feature modules must not deep-import another feature module";
  }

  const sharedImportsOwnedCode =
    source === "@/app" ||
    source.startsWith("@/app/") ||
    source === "@/modules" ||
    source.startsWith("@/modules/") ||
    Boolean(importedModule);
  if (normalizedImporter.includes("/src/shared/") && sharedImportsOwnedCode) {
    return "shared web code must not import routes or feature modules";
  }

  return undefined;
}

async function sourceFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(
    entries.map(async (entry) => {
      const target = path.join(directory, entry.name);
      if (entry.isDirectory()) return sourceFiles(target);
      return entry.isFile() && SOURCE_FILE.test(entry.name) ? [target] : [];
    }),
  );
  return nested.flat();
}

export async function checkWebBoundaries(sourceRoot) {
  const violations = [];
  for (const file of await sourceFiles(sourceRoot)) {
    const content = await readFile(file, "utf8");
    for (const match of content.matchAll(IMPORT_SOURCE)) {
      const source = match[1];
      if (!source) continue;
      const reason = boundaryViolation(file, source);
      if (reason)
        violations.push(
          `${normalize(path.relative(sourceRoot, file))}: ${reason}: ${source}`,
        );
    }
  }
  return violations;
}

const invokedPath = process.argv[1] ? path.resolve(process.argv[1]) : "";
if (invokedPath === fileURLToPath(import.meta.url)) {
  const sourceRoot = path.resolve(process.argv[2] ?? "src");
  const violations = await checkWebBoundaries(sourceRoot);
  if (violations.length > 0) {
    console.error(violations.join("\n"));
    process.exitCode = 1;
  }
}
