const { test, expect } = require("@playwright/test");
const owner = "ui-test-owner-" + "x".repeat(40);
test("owner can inspect console and create a scheduled draft without publishing", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page).toHaveTitle("Telegram Agent Control");
  await page.locator("#key").fill(owner);
  await page.locator("#login-form button").click();
  await expect(page.locator(".hero")).toBeVisible();
  await expect(page.locator(".hero")).toContainText("185 methods");
  await page.screenshot({
    path: "test-results/console-desktop.png",
    fullPage: true,
  });
  await page.locator('[data-view="compose"]').click();
  await page
    .locator("#payload")
    .fill(JSON.stringify({ chat_id: "@ui_test", text: "سلام از تست کنسول" }));
  await page.locator("#validate").click();
  await expect(page.locator("#notice")).toContainText("passed");
  await page.locator("#create").click();
  await expect(page.locator("#detail")).toBeVisible();
  await expect(page.locator("#detail-body")).toContainText("draft");
  await page.locator("#close-detail").click();
  await page.locator('[data-view="methods"]').click();
  await page.locator("#search-method").fill("sendRichMessage");
  await expect(page.locator('[data-method="sendRichMessage"]')).toBeVisible();
  await page.locator('[data-method="sendRichMessage"]').click();
  await expect(page.locator("#detail-body")).toContainText(
    "InputRichBlockSlideshow",
  );
  await page.locator("#close-detail").click();
  for (const view of [
    "operations",
    "automations",
    "emojis",
    "logs",
    "database",
  ]) {
    await page.locator(`[data-view="${view}"]`).click();
    await expect(page.locator("#content")).toBeVisible();
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('[data-view="overview"]').click();
  await page.screenshot({
    path: "test-results/console-mobile.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
test("remote MCP can call the authenticated REST diagnostics", async ({
  request,
}) => {
  const response = await request.post("/mcp/", {
    headers: {
      Authorization: "Bearer " + "ui-test-agent-" + "x".repeat(40),
      Accept: "application/json, text/event-stream",
    },
    data: {
      jsonrpc: "2.0",
      id: 2,
      method: "tools/call",
      params: { name: "inspect_system", arguments: {} },
    },
  });
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.error).toBeUndefined();
  expect(body.result.isError).not.toBe(true);
  expect(JSON.stringify(body.result)).toContain("185");
});
