const { defineConfig, devices } = require("@playwright/test");
module.exports = defineConfig({
  testDir: "tests/ui",
  timeout: 30000,
  workers: 1,
  projects: [
    { name: "chromium", use: { browserName: "chromium" } },
    { name: "iphone-webkit", use: { ...devices["iPhone 13"], browserName: "webkit" } },
  ],
  use: { baseURL: "http://127.0.0.1:8790", headless: true },
  webServer: {
    command: ".venv/bin/python scripts/ui_server.py",
    url: "http://127.0.0.1:8790/health/live",
    reuseExistingServer: !process.env.CI,
  },
  reporter: "list",
});
