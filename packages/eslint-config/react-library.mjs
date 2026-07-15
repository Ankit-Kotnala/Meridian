import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const reactLibraryVitals = nextVitals.map((configuration) => ({
  ...configuration,
  rules: Object.fromEntries(
    Object.entries(configuration.rules ?? {}).filter(
      ([ruleName]) => !ruleName.startsWith("@next/next/"),
    ),
  ),
}));

export default defineConfig([
  ...reactLibraryVitals,
  ...nextTypescript,
  {
    files: ["src/**/*.{js,jsx,ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["next", "next/**", "@/**", "@careeros/contracts"],
              message:
                "Generic UI must not depend on Next, web aliases, or API contracts.",
            },
          ],
        },
      ],
    },
  },
  globalIgnores(["dist/**", "coverage/**"]),
]);
