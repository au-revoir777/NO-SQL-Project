import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const config = [
  ...nextVitals,
  ...nextTs,
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "next-env.d.ts",
      "src/lib/api/schema.d.ts",
      "coverage/**",
    ],
  },
  {
    rules: {
      // Components use CSS tokens only (design system): no hex colours in TSX.
      // shadcn's CLI rewrites imports to the "cn" package; use the pinned helper instead.
      "no-restricted-imports": [
        "error",
        { paths: [{ name: "cn", message: 'Import { cn } from "@/lib/utils".' }] },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: "Literal[value=/#[0-9a-fA-F]{3,8}\\b/]",
          message: "Use a CSS colour token (var(--...)) instead of a hex value.",
        },
      ],
    },
  },
];

export default config;
