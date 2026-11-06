import { defineConfig } from "@playwright/test";

/**
 * End-to-end demo script (GOAL Section C) against the running compose stack.
 * Start it first with `.\demo.ps1 up` (or `.\demo.ps1 reset`), then:
 *   npx playwright test
 * Uses the installed Microsoft Edge, so no browser download is needed.
 */
export default defineConfig({
  testDir: "e2e",
  timeout: 6 * 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["json", { outputFile: "docs/verification/e2e/results.json" }]],
  outputDir: "docs/verification/e2e/artifacts",
  use: {
    baseURL: process.env.SMARTOPS_E2E_BASE_URL ?? "http://localhost:3000",
    channel: process.env.SMARTOPS_E2E_CHANNEL ?? "msedge",
    viewport: { width: 1366, height: 768 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
