const { test, expect } = require("@playwright/test");
const owner = "ui-test-owner-" + "x".repeat(40);
test("owner can inspect console and create a scheduled draft without publishing", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page).toHaveTitle("Telegram Agent Control");
  await page.locator("#login summary").click();
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

test("owner creates scoped credential, validates buttons and revokes through approval", async ({
  page,
  request,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.locator("#login summary").click();
  await page.locator("#key").fill(owner);
  await page.locator("#login-form button").click();
  await page.locator('[data-view="agents"]').click();
  const name = "Browser agent " + Date.now();
  await page.locator("#grant-name").fill(name);
  await page.locator("#grant-role").selectOption("READ");
  await page.locator("#grant-create").click();
  await page
    .getByRole("button", { name: "Create this grant", exact: true })
    .click();
  await expect(page.locator("#detail-body")).toContainText(
    "Credential created",
  );
  const text = await page.locator("#detail-body pre").innerText();
  const result = JSON.parse(text);
  const authorization = { Authorization: "Bearer " + result.credential };
  expect(
    (await request.get("/v1/system", { headers: authorization })).status(),
  ).toBe(200);
  expect(
    (
      await request.post("/v1/operations", {
        headers: authorization,
        data: {
          method: "sendMessage",
          payload: { chat_id: "@ui_test", text: "denied" },
          idempotency_key: "browser-denied-" + Date.now(),
        },
      })
    ).status(),
  ).toBe(403);
  await page.locator("#close-detail").click();
  await expect(page.locator("#detail-body")).toBeEmpty();
  await page.locator('[data-view="keyboards"]').click();
  await page.locator("#button-style-1").selectOption("primary");
  await page.locator("#keyboard-build").click();
  await expect(page.locator("#keyboard-result")).toContainText(
    "inline_keyboard",
  );
  await expect(page.locator("#keyboard-result")).toContainText("primary");
  await page.locator('[data-view="media"]').click();
  await page
    .locator("#library-upload")
    .setInputFiles({
      name: "browser-fixture.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("No external delivery"),
    });
  await expect(page.locator("#content")).toContainText("browser-fixture.txt");
  for (const view of ["channels", "diagnostics", "settings", "maintenance"]) {
    await page.locator(`[data-view="${view}"]`).click();
    await expect(page.locator("#content .card").first()).toBeVisible();
  }
  await page.locator('[data-view="agents"]').click();
  await page.locator(`[data-revoke="${result.grant.id}"]`).click();
  await page
    .getByRole("button", {
      name: "Approve these exact parameters",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: "Execute approved request", exact: true })
    .click();
  await expect(page.locator("#detail-body")).toContainText("executed");
  expect(
    (await request.get("/v1/system", { headers: authorization })).status(),
  ).toBe(401);
  expect(errors).toEqual([]);
});


test("mobile password login, connection discovery, key creation and logout", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.locator("#username").fill("ui-owner");
  await page.locator("#password").fill("ui-password-for-tests");
  await page.locator("#password-form button").click();
  await expect(page.locator("#content")).toBeVisible();
  await page.reload();
  await expect(page.locator("#content")).toBeVisible();
  await page.locator('[data-view="connections"]').click();
  await expect(page.locator("#agent-instruction")).toHaveValue(/agent-guide/);
  await page.screenshot({ path: "test-results/mobile-connections.png", fullPage: true });
  await page.locator("#new-api-key").click();
  await page.locator("#grant-name").fill("Mobile API assistant");
  await page.locator("#grant-create").click();
  await page.getByRole("button", { name: "Create this grant", exact: true }).click();
  await expect(page.locator("#detail-body")).toContainText("tac_");
  await page.locator("#close-detail").click();
  await page.locator("#disconnect").click();
  await page.reload();
  await expect(page.locator("#password-form")).toBeVisible();
  await expect(page.locator("#content")).toBeHidden();
});
