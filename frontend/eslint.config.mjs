import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  // ── Module boundary enforcement (Task 0A.7) ──────────────
  // Modules must import from other modules via their barrel index.ts
  // NOT from internal components/hooks/types files directly.
  {
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/modules/*/components/*", "@/modules/*/hooks/*", "@/modules/*/types/*"],
              message:
                "Import from the module barrel (@/modules/<name>) instead of internal files. Module boundary rule.",
            },
          ],
        },
      ],
    },
  },
]);

export default eslintConfig;
