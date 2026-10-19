import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  use: {
    baseURL: process.env.TOFSCOPE_TEST_URL || "http://127.0.0.1:18763",
    headless: true,
    channel: "chrome",
  },
  webServer: process.env.TOFSCOPE_TEST_URL
    ? undefined
    : [
        {
          command: "npm run dev",
          url: "http://127.0.0.1:18763",
          reuseExistingServer: false,
        },
        {
          command: "../.venv/bin/python ../scripts/e2e_server.py",
          url: "http://127.0.0.1:18764/healthz",
          reuseExistingServer: false,
        },
      ],
  reporter: "list",
});
