import { execFileSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import * as prettier from "prettier";

const mode = process.argv[2];
if (!new Set(["--check", "--write"]).has(mode)) {
  console.error("Usage: node scripts/run-prettier.mjs --check|--write");
  process.exit(2);
}

const repositoryRoot = fileURLToPath(new URL("..", import.meta.url));
process.chdir(repositoryRoot);

const listedFiles = execFileSync(
  "git",
  ["ls-files", "--cached", "--others", "--exclude-standard", "-z"],
  { cwd: repositoryRoot },
)
  .toString("utf8")
  .split("\0")
  .filter(Boolean)
  .sort();

const changed = [];
for (const file of listedFiles) {
  const info = await prettier.getFileInfo(file, {
    ignorePath: [".gitignore", ".prettierignore"],
  });
  if (info.ignored || info.inferredParser === null) continue;

  const input = await readFile(file, "utf8");
  const config =
    (await prettier.resolveConfig(file, { editorconfig: true })) ?? {};
  const formatted = await prettier.format(input, { ...config, filepath: file });
  if (formatted === input) continue;

  changed.push(file);
  if (mode === "--write") await writeFile(file, formatted, "utf8");
}

if (changed.length === 0) {
  console.log("All repository files use Prettier code style.");
  process.exit(0);
}

for (const file of changed) console.log(file);
if (mode === "--check") {
  console.error(`Code style issues found in ${changed.length} file(s).`);
  process.exit(1);
}
console.log(`Formatted ${changed.length} file(s).`);
