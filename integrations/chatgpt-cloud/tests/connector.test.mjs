import { test } from "node:test";
import assert from "node:assert/strict";
import {
  TOOLS,
  execute,
  rpc,
  seal,
  unseal,
  saveConnection,
  imageURL,
  importImage,
  gateway,
  readLimited,
} from "../lib/connector.mjs";
const token = "tac_" + "test_".repeat(10),
  user = "test-owner";
function database() {
  const rows = new Map();
  return {
    rows,
    prepare(sql) {
      return {
        bind(...args) {
          return {
            async first() {
              return rows.has(args[0]) ? { secret: rows.get(args[0]) } : null;
            },
            async run() {
              if (sql.startsWith("DELETE")) rows.delete(args[0]);
              else rows.set(args[0], args[1]);
            },
          };
        },
      };
    },
  };
}
function environment() {
  return {
    DB: database(),
    TAC_BASE_URL: "https://gateway.example",
    CREDENTIAL_VAULT_KEY: btoa("a".repeat(32)),
  };
}
async function linked() {
  const env = environment();
  env.DB.rows.set(user, await seal(env, user, token));
  return env;
}
const json = (x, status = 200) => Response.json(x, { status });
const msg = (name, args = {}, who = user) =>
  new Request("https://connector.example/mcp", {
    method: "POST",
    headers: {
      ...(who ? { "oai-authenticated-user-id": who } : {}),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/call",
      params: { name, arguments: args },
    }),
  });
const never = async () => {
  throw Error("Unexpected upstream call");
};
test("discovery supplies typed tools without exposing admin endpoints", async () => {
  const env = environment();
  for (const method of ["server/discover", "initialize", "tools/list"]) {
    const r = await rpc(
      new Request("https://connector.example/mcp", {
        method: "POST",
        body: JSON.stringify({ jsonrpc: "2.0", id: 1, method }),
      }),
      env,
      never,
    );
    const body = await r.json();
    assert.ok(body.result);
  }
  assert.equal(TOOLS.length, 12);
  assert.ok(!TOOLS.some((t) => /approve|shell|credential|deploy/.test(t.name)));
});
test("missing identity and unconnected user cannot invoke gateway", async () => {
  const env = await linked();
  assert.ok(
    (await (await rpc(msg("inspect_system", {}, null), env, never)).json())
      .error,
  );
  assert.equal(
    (await (await rpc(msg("inspect_system", {}, "other"), env, never)).json())
      .result.isError,
    true,
  );
});
test("credentials encrypted, identity bound, and never in status", async () => {
  const env = await linked();
  const encrypted = env.DB.rows.get(user);
  assert.ok(!encrypted.includes(token));
  assert.equal(await unseal(env, user, encrypted), token);
  await assert.rejects(() => unseal(env, "other", encrypted));
  assert.ok(
    !JSON.stringify(
      await execute(env, user, "connection_status", {}, never),
    ).includes(token),
  );
});
test("setup rejects owner and legacy credentials", async () => {
  for (const identity of ["owner", "agent"]) {
    const env = environment();
    await assert.rejects(() =>
      saveConnection(env, user, token, async () =>
        json({ role: identity, identity }),
      ),
    );
    assert.equal(env.DB.rows.size, 0);
  }
  await assert.rejects(() =>
    saveConnection(environment(), user, "owner-" + "x".repeat(40), never),
  );
});
test("setup verifies scoped identity before committing encrypted credential", async () => {
  const env = environment();
  const saved = await saveConnection(env, user, token, async () =>
    json({
      role: "agent",
      identity: "agent:" + "a".repeat(32),
      allowed_chats: ["@test"],
    }),
  );
  assert.equal(saved.connected, true);
  assert.equal(await unseal(env, user, env.DB.rows.get(user)), token);
});
test("unknown tool, arbitrary path and extra approval fields fail closed", async () => {
  const env = await linked();
  for (const [name, args] of [
    ["approve_operation", {}],
    ["operation_status", { operation_id: "../approve" }],
    [
      "prepare_operation",
      {
        method: "sendMessage",
        payload: {},
        idempotency_key: "test-key-1",
        approved: true,
      },
    ],
    [
      "prepare_operation",
      {
        method: "promoteChatMember",
        payload: {},
        idempotency_key: "test-key-1",
      },
    ],
  ])
    await assert.rejects(() => execute(env, user, name, args, never));
});
test("scheduled draft preserves key offset and independent review URL", async () => {
  const env = await linked();
  const args = {
    method: "sendMessage",
    payload: { chat_id: "@test", text: "سلام" },
    idempotency_key: "plan-2026-10-10-1",
    run_at: "2026-10-10T18:00:00+03:30",
  };
  let seen;
  const result = await execute(
    env,
    user,
    "prepare_operation",
    args,
    async (url, init) => {
      seen = JSON.parse(init.body);
      assert.equal(url, "https://gateway.example/v1/operations");
      assert.equal(init.headers.Authorization, "Bearer " + token);
      return json({
        id: "a".repeat(32),
        status: "draft",
        digest: "b".repeat(64),
      });
    },
  );
  assert.deepEqual(seen, args);
  assert.equal(result.approval_required, true);
  assert.match(result.owner_review_url, /\?review=a{32}$/);
  await assert.rejects(() =>
    execute(
      env,
      user,
      "prepare_operation",
      { ...args, run_at: "2026-10-10T18:00:00" },
      never,
    ),
  );
});
test("daily plan stops on partial/uncertain request, never retries", async () => {
  const env = await linked();
  let n = 0;
  const posts = [1, 2, 3].map((i) => ({
    method: "sendMessage",
    payload: { chat_id: "@test", text: String(i) },
    idempotency_key: "plan-key-" + i,
  }));
  const result = await execute(
    env,
    user,
    "prepare_content_plan",
    { posts },
    async () => {
      n++;
      if (n === 2) throw Error(token);
      return json({ id: "a".repeat(32), status: "draft" });
    },
  );
  assert.equal(n, 2);
  assert.equal(result.complete, false);
  assert.equal(result.items[1].state, "unconfirmed");
  assert.ok(!JSON.stringify(result).includes(token));
});
test("uncertain statuses returned without any automatic resend", async () => {
  let n = 0;
  const x = await execute(
    await linked(),
    user,
    "operation_status",
    { operation_id: "a".repeat(32) },
    async () => {
      n++;
      return json({ id: "a".repeat(32), status: "uncertain" });
    },
  );
  assert.equal(n, 1);
  assert.equal(x.status, "uncertain");
});
test("quota, denied, expired and redirects do not leak response secrets", async () => {
  for (const status of [401, 403, 429, 500, 302]) {
    await assert.rejects(
      () =>
        gateway(
          environment(),
          token,
          "GET",
          "/v1/system",
          undefined,
          async () => json({ detail: token }, status),
        ),
      (e) => !e.message.includes(token),
    );
  }
  await assert.rejects(
    () =>
      gateway(
        environment(),
        token,
        "GET",
        "/v1/system",
        undefined,
        async () =>
          new Response("<h1>Site Unavailable</h1>", {
            headers: { "Content-Type": "text/html" },
          }),
      ),
    /non-JSON/,
  );
});
test("secret-bearing successful responses are sanitized", async () => {
  const x = await gateway(
    environment(),
    token,
    "GET",
    "/v1/system",
    undefined,
    async () => json({ fake: token }),
  );
  assert.equal(x.fake, "[REDACTED]");
});
test("image import blocks SSRF, credentials, ports and fabricated sandbox links", () => {
  for (const url of [
    "http://files.oaiusercontent.com/a",
    "https://127.0.0.1/a",
    "https://files.oaiusercontent.com.evil.example/a",
    "https://files.oaiusercontent.com@evil.example/a",
    "https://files.oaiusercontent.com:444/a",
    "sandbox:/mnt/data/a.png",
  ])
    assert.throws(() => imageURL(url));
  assert.equal(
    imageURL("https://files.oaiusercontent.com/a?sig=test"),
    "https://files.oaiusercontent.com/a?sig=test",
  );
});
test("image fetch never receives TAC auth; upload only to fixed gateway", async () => {
  const calls = [];
  const result = await importImage(
    environment(),
    token,
    {
      download_url: "https://files.oaiusercontent.com/test",
      filename: "x.png",
    },
    async (url, init) => {
      calls.push(url);
      assert.equal(init.redirect, "error");
      if (calls.length === 1) {
        assert.equal(init.headers, undefined);
        return new Response(new Uint8Array([137, 80, 78, 71]), {
          headers: { "Content-Type": "image/png" },
        });
      }
      assert.equal(init.headers.Authorization, "Bearer " + token);
      return json({ id: "a".repeat(32) });
    },
  );
  assert.equal(result.id, "a".repeat(32));
  assert.deepEqual(calls, [
    "https://files.oaiusercontent.com/test",
    "https://gateway.example/v1/assets",
  ]);
});
test("streaming size bound works without content length", async () => {
  await assert.rejects(
    () => readLimited(new Response("abcdef"), 4),
    /size limit/,
  );
});
test("oversized malformed MCP input is rejected without tools execution", async () => {
  for (const body of ["bad", "x".repeat(33000)]) {
    const r = await rpc(
      new Request("https://connector.example/mcp", { method: "POST", body }),
      environment(),
      never,
    );
    assert.equal(r.status, 400);
  }
});
