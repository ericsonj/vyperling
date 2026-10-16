import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    environment: "node",
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      // Only the pure, vscode-free modules are exercised by unit tests; the
      // vscode-coupled files are verified manually via the F5 dev host.
      include: ["src/discovery.ts", "src/paths.ts", "src/forgeConfig.ts"],
      // Report-only: no thresholds gate (young codebase).
    },
  },
});
