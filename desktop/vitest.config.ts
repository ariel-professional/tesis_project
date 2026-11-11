import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  esbuild: { jsx: "automatic" },
  resolve: {
    alias: {
      "@domain-ui-sdk": path.resolve(__dirname, "domain-ui-sdk/src/index.ts"),
      "@domain-ui-kit": path.resolve(__dirname, "domain-ui-kit/src/index.ts"),
      "@srfl-ui": path.resolve(
        __dirname,
        "../src/tesis_domain_extensions/domains/single_row_facility_layout/ui/src",
      ),
      "react/jsx-dev-runtime": path.resolve(
        __dirname,
        "node_modules/react/jsx-dev-runtime.js",
      ),
      "react/jsx-runtime": path.resolve(__dirname, "node_modules/react/jsx-runtime.js"),
      react: path.resolve(__dirname, "node_modules/react/index.js"),
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
