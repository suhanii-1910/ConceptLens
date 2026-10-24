import { existsSync, realpathSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const frontendRoot = dirname(fileURLToPath(import.meta.url));

/**
 * Summon Fixer is deliberately opt-in and dev-only. It is built in a separate
 * local monorepo, not downloaded from npm or bundled into ConceptLens.
 *
 * Start through the Summon CLI from ConceptLens/frontend so its engine's
 * workspace root matches Vite's source-registry root (src/... paths).
 */
export default defineConfig(async ({ command }) => {
  const summonEnabled =
    command === "serve" &&
    process.env.VITEST !== "true" &&
    process.env.CONCEPTLENS_SUMMON === "1";

  const plugins = [react()];
  let summonRoot: string | undefined;

  if (summonEnabled) {
    const configuredRoot = process.env.SUMMON_FIXER_ROOT;
    if (!configuredRoot) {
      throw new Error(
        "CONCEPTLENS_SUMMON=1 requires SUMMON_FIXER_ROOT to point to a built local Summon-Fixer- checkout.",
      );
    }

    summonRoot = realpathSync(resolve(configuredRoot));
    const vitePluginFile = resolve(summonRoot, "packages/vite-plugin/dist/index.js");
    const overlayFile = resolve(summonRoot, "packages/overlay/dist/index.js");

    if (!existsSync(vitePluginFile) || !existsSync(overlayFile)) {
      throw new Error(
        "Summon Fixer build outputs are missing. Run 'npm ci && npm run build' in SUMMON_FIXER_ROOT first.",
      );
    }

    const { summonFixer } = await import(pathToFileURL(vitePluginFile).href);
    // Instrument before React's transformation; never affect production builds.
    plugins.unshift(summonFixer({ workspaceRoot: frontendRoot }));
  }

  return {
    plugins,
    ...(summonRoot
      ? {
          resolve: {
            alias: {
              // The injected virtual client imports this package by name.
              "@summon-fixer/overlay": resolve(summonRoot, "packages/overlay/dist/index.js"),
            },
          },
        }
      : {}),
    server: {
      host: "127.0.0.1",
      port: 5174,
      strictPort: true,
      // External file serving is enabled only for trusted local Summon sources.
      ...(summonRoot ? { fs: { allow: [frontendRoot, summonRoot] } } : {}),
      proxy: {
        "/api": {
          target: process.env.CONCEPTLENS_API_PROXY_TARGET || "http://127.0.0.1:8001",
          changeOrigin: true,
          rewrite: (path: string) => path.replace(/^\/api/, ""),
        },
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      include: ["src/**/*.test.{ts,tsx}"],
      restoreMocks: true,
    },
  };
});
