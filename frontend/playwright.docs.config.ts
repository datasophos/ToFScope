import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./docs-capture",
  workers: 1,
  timeout: 120_000,
  use: {
    baseURL: "http://127.0.0.1:18765",
    viewport: { width: 1660, height: 1100 },
    deviceScaleFactor: 1,
    locale: "en-US",
    timezoneId: "UTC",
    colorScheme: "light",
    channel: "chromium",
    headless: true,
  },
  webServer: {
    command: "python ../scripts/docs_capture/server.py",
    url: "http://127.0.0.1:18765/healthz",
    reuseExistingServer: false,
    timeout: 180_000,
  },
  reporter: "list",
});
