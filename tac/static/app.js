"use strict";
let csrf = "";
let key = "",
  role = "",
  view = "overview",
  paused = false,
  emojiOffset = 0,
  emojiQuery = "",
  emojiPack = "";
const $ = (s) => document.querySelector(s),
  content = $("#content");
const titles = {
  overview: "Overview",
  operations: "Operations",
  compose: "Compose",
  automations: "Automations",
  emojis: "Emoji studio",
  methods: "API explorer",
  logs: "Activity & logs",
  database: "Database",
};
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
function notice(msg, error = false) {
  $("#notice").hidden = false;
  $("#notice").className = error ? "error" : "";
  $("#notice").textContent = msg;
}
async function api(path, method = "GET", body) {
  const r = await fetch("/v1/" + path, {
    method,
    headers: {
      ...(key ? { Authorization: "Bearer " + key } : {}),
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
      ...(body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
    },
    body: body
      ? body instanceof FormData
        ? body
        : JSON.stringify(body)
      : undefined,
  });
  let data;
  try {
    data = await r.json();
  } catch {
    throw Error("Invalid server response");
  }
  if (!r.ok)
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
}
async function act(fn) {
  try {
    await fn();
  } catch (e) {
    notice(e.message, true);
  }
}
function table(head, rows) {
  return `<div class="card scroll"><table><thead><tr>${head.map((x) => `<th>${esc(x)}</th>`).join("")}</tr></thead><tbody>${rows.join("") || `<tr><td colspan="${head.length}" class="empty">No records yet.</td></tr>`}</tbody></table></div>`;
}
function status(s) {
  return `<span class="badge ${esc(s)}">${esc(s)}</span>`;
}
function pretty(v) {
  return `<pre>${esc(JSON.stringify(v, null, 2))}</pre>`;
}
function btn(text, fn, style = "") {
  const b = document.createElement("button");
  b.textContent = text;
  b.className = style;
  b.onclick = () => act(fn);
  return b;
}
async function load() {
  if (!key && !csrf) return;
  $("#title").textContent = titles[view];
  document
    .querySelectorAll("nav button")
    .forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  document.body.classList.toggle("chat-mode", view === "assistant");
  await pages[view]();
}
$("#login-form").onsubmit = (e) => {
  e.preventDefault();
  act(async () => {
    key = $("#key").value;
    const s = await api("system");
    role = s.role;
    $("#key").value = "";
    $("#login").hidden = true;
    content.hidden = false;
    $("#connection").textContent = "● Connected · " + role;
    await load();
  });
};
async function connected() {
  const s = await api("system");
  role = s.role;
  $("#login").hidden = true;
  content.hidden = false;
  $("#connection").textContent = "● Connected · " + role;
  await load();
}
$("#password-form").onsubmit = (e) => {
  e.preventDefault();
  act(async () => {
    key = "";
    const result = await api("session", "POST", {
      username: $("#username").value, password: $("#password").value,
    });
    $("#password").value = "";
    csrf = result.csrf;
    await connected();
  });
};
$("#disconnect").onclick = () => act(async () => {
  if (csrf) await api("session", "DELETE");
  key = ""; csrf = ""; role = "";
  content.innerHTML = "";
  $("#detail-body").innerHTML = "";
  $("#detail").close();
  content.hidden = true;
  $("#login").hidden = false;
  $("#connection").textContent = "● Disconnected";
});
window.addEventListener("DOMContentLoaded", async () => {
  try {
    const session = await api("session");
    csrf = session.csrf;
    await connected();
  } catch { /* Signed out, or server unavailable: keep the login form visible. */ }
});
$("#refresh").onclick = () => act(load);
$("#nav").onclick = (e) => {
  if (e.target.dataset.view) {
    view = e.target.dataset.view;
    act(load);
  }
};
$("#close-detail").onclick = () => $("#detail").close();
$("#pause").onclick = () =>
  act(async () => {
    await api("system/pause?enabled=" + !paused, "POST");
    paused = !paused;
    notice(
      paused
        ? "Execution paused. Running requests may finish."
        : "Execution resumed.",
    );
    await load();
  });
let operationTimer;
async function showOperation(id) {
  clearTimeout(operationTimer);
  const o = await api("operations/" + id);
  const box = $("#detail-body");
  box.innerHTML = view === "assistant"
    ? `<section dir="rtl" lang="fa"><h3>بررسی مستقل عملیات</h3><p dir="auto">${esc(o.method)} · ${esc(o.payload.chat_id || "بدون مقصد کانال")}</p><p>وضعیت: ${esc(o.status)}</p><p class="chat-reply">${esc(o.payload.text || o.payload.caption || "عملیات بدون متن؛ داده‌های کامل را بررسی کنید.")}</p><details><summary>داده‌های کامل و زمان اجرا</summary>${pretty(o)}</details></section>`
    : pretty(o);
  const actions = document.createElement("div");
  actions.className = "actions";
  if (o.status === "draft" && role === "owner")
    actions.append(
      btn(
        "Approve this exact revision",
        async () => {
          await api("operations/" + id + "/approve", "POST", {
            expected_digest: o.digest,
          });
          notice("Approved and queued.");
          await showOperation(id);
          await load();
        },
        "primary",
      ),
    );
  if (["draft", "queued"].includes(o.status)) {
    actions.append(
      btn("Edit payload", async () => {
        const p = prompt("JSON payload", JSON.stringify(o.payload, null, 2));
        if (p === null) return;
        await api("operations/" + id, "PATCH", {
          payload: JSON.parse(p),
          attachments: o.attachments,
          expected_digest: o.digest,
        });
        await showOperation(id);
      }),
    );
    actions.append(
      btn(
        "Cancel",
        async () => {
          await api("operations/" + id + "/cancel", "POST");
          await showOperation(id);
          await load();
        },
        "danger",
      ),
    );
  }
  box.prepend(actions);
  $("#detail").showModal();
  if (["queued", "running"].includes(o.status)) operationTimer=setTimeout(()=>{if($("#detail").open)act(()=>showOperation(id));},1500);
}
const templates = {
  sendMessage: {
    chat_id: "@your_channel",
    text: "Hello from Telegram Agent Control",
  },
  sendPhoto: {
    chat_id: "@your_channel",
    photo: "attach://photo",
    caption: "Your caption",
    reply_markup: {
      inline_keyboard: [
        [{ text: "🌐 Open", url: "https://t.me", style: "primary" }],
      ],
    },
  },
  sendMediaGroup: {
    chat_id: "@your_channel",
    media: [
      { type: "photo", media: "attach://slide1" },
      { type: "photo", media: "attach://slide2" },
    ],
  },
  sendRichMessage: {
    chat_id: "@your_channel",
    rich_message: {
      is_rtl: true,
      html: '<h1>عنوان اسلاید</h1><tg-slideshow><img src="https://example.com/one.jpg"/><img src="https://example.com/two.jpg"/></tg-slideshow>',
    },
  },
  pinChatMessage: { chat_id: "@your_channel", message_id: 1 },
  unpinChatMessage: { chat_id: "@your_channel", message_id: 1 },
  deleteMessage: { chat_id: "@your_channel", message_id: 1 },
  editMessageCaption: {
    chat_id: "@your_channel",
    message_id: 1,
    caption: "Updated caption",
  },
  getMe: {},
  getChatMember: { chat_id: "@your_channel", user_id: 1 },
  getStickerSet: { name: "FinanceEmoji" },
};
const pages = {
  async overview() {
    const s = await api("system");
    paused = s.paused.enabled;
    $("#pause").textContent = paused ? "Resume execution" : "Pause execution";
    $("#pause").disabled = role !== "owner";
    content.innerHTML = `<div class="hero"><div class="tag">YOUR TELEGRAM WORKSPACE</div><h2>One control plane. Every operation.</h2><p>Compose, approve and schedule. Give your agent documented tools and keep a clear record of every action.</p><span class="badge">Bot API ${esc(s.api_version)}</span> <span class="badge">${s.methods} methods · ${s.types} types</span></div><div class="grid">${[
      ["Queued", s.operations.queued || 0],
      ["Need approval", s.operations.draft || 0],
      ["Succeeded", s.operations.succeeded || 0],
      [
        "Need attention",
        (s.operations.failed || 0) + (s.operations.uncertain || 0),
      ],
    ]
      .map(
        ([l, n]) =>
          `<div class="card"><div class="label">${l}</div><div class="stat">${n}</div></div>`,
      )
      .join(
        "",
      )}</div><div class="split"><div class="card"><h2>Connection & permissions</h2><p>Bot credential: ${s.bot_configured ? "Configured" : "Not configured"}</p><p>Allowed targets: ${esc(s.allowed_chats.join(", ") || "None configured")}</p><p>Role: ${esc(s.role)}</p><p>Worker heartbeat: ${esc(s.worker?.heartbeat || "Waiting for worker")}</p></div><div class="card"><h2>Start here</h2><p>Verify getMe and getChatMember in the API explorer. Upload media in Compose, review the payload and approve it as the owner.</p><p>Use the MCP bridge to connect an external agent. Audit logs and database counts are available through the same API.</p><a href="/docs">Open interactive API docs ↗</a></div></div>`;
  },
  async operations() {
    const ops = await api("operations");
    content.innerHTML = table(
      ["Method / ID", "Status", "Scheduled", "Attempts", "Action"],
      ops.map(
        (o) =>
          `<tr><td><b>${esc(o.method)}</b><br><code>${esc(o.id.slice(0, 12))}</code></td><td>${status(o.status)}</td><td>${esc(new Date(o.run_at).toLocaleString())}</td><td>${o.attempts}</td><td><button data-id="${o.id}">Inspect</button></td></tr>`,
      ),
    );
    content
      .querySelectorAll("[data-id]")
      .forEach(
        (b) => (b.onclick = () => act(() => showOperation(b.dataset.id))),
      );
  },
  async compose() {
    content.innerHTML = `<div class="split"><div class="card"><h2>Create an operation</h2><p class="help">All Telegram methods are available in the API explorer. Writes require owner approval.</p><label>Template</label><select id="template">${Object.keys(
      templates,
    )
      .map((n) => `<option>${n}</option>`)
      .join(
        "",
      )}</select><label>Method</label><input id="method" value="sendMessage"><label>Payload JSON</label><textarea id="payload" rows="13"></textarea><label>Schedule (your browser timezone; optional)</label><input id="run-at" type="datetime-local"><label>Attachment bindings JSON</label><textarea id="bindings" style="min-height:60px">{}</textarea><div class="actions"><button id="validate">Validate</button><button id="create" class="primary">Save operation</button></div></div><div><div class="card"><h2>Content preview</h2><p class="help">Text preview only. Use a test channel to verify Telegram's native rendering.</p><div id="post-preview" class="preview"></div></div><div class="card"><h2>Media library</h2><p>Upload a file, then bind its asset ID to the name in attach://name.</p><input id="upload" type="file"><div id="upload-result"></div></div></div></div>`;
    const refresh = () => {
      try {
        const p = JSON.parse($("#payload").value);
        $("#post-preview").textContent =
          p.text ||
          p.caption ||
          p.rich_message?.html ||
          JSON.stringify(p.media || p, null, 2);
      } catch {
        $("#post-preview").textContent = "Enter valid JSON to preview.";
      }
    };
    $("#payload").value = JSON.stringify(templates.sendMessage, null, 2);
    $("#payload").oninput = refresh;
    $("#template").onchange = () => {
      $("#method").value = $("#template").value;
      $("#payload").value = JSON.stringify(
        templates[$("#template").value],
        null,
        2,
      );
      refresh();
    };
    refresh();
    $("#validate").onclick = () =>
      act(async () => {
        await api("validate", "POST", {
          method: $("#method").value,
          payload: JSON.parse($("#payload").value),
        });
        notice(
          "Schema validation passed. Destination and permission checks still apply.",
        );
      });
    $("#create").onclick = () =>
      act(async () => {
        const o = await api("operations", "POST", {
          method: $("#method").value,
          payload: JSON.parse($("#payload").value),
          attachments: JSON.parse($("#bindings").value),
          run_at: $("#run-at").value
            ? new Date($("#run-at").value).toISOString()
            : null,
          idempotency_key: crypto.randomUUID(),
        });
        notice("Operation saved: " + o.status);
        await showOperation(o.id);
      });
    $("#upload").onchange = () =>
      act(async () => {
        const f = $("#upload").files[0];
        if (!f) return;
        const form = new FormData();
        form.append("file", f);
        const a = await api("assets", "POST", form);
        $("#upload-result").innerHTML = pretty(a);
      });
  },
  async methods() {
    const d = await api("capabilities");
    content.innerHTML =
      '<div class="card"><h2>Bot API ' +
      esc(d.version) +
      '</h2><input id="search-method" placeholder="Search a method or capability…"><p class="help">Generated from the official specification. Select a method to read the complete nested schema.</p></div><div class="method-list" id="method-list"></div>';
    const render = (q) => {
      $("#method-list").innerHTML = d.methods
        .filter((m) =>
          (m.name + " " + m.description)
            .toLowerCase()
            .includes(q.toLowerCase()),
        )
        .map(
          (m) =>
            `<button class="method" data-method="${esc(m.name)}"><b>${esc(m.name)}</b><small>${esc(m.description.slice(0, 140))}</small><small>${esc(m.effect)}</small></button>`,
        )
        .join("");
      $("#method-list")
        .querySelectorAll("button")
        .forEach(
          (b) =>
            (b.onclick = () =>
              act(async () => {
                const m = await api("methods/" + b.dataset.method);
                $("#detail-body").innerHTML =
                  `<h3>${esc(b.dataset.method)}</h3><a href="${esc(m.source)}" target="_blank">Official documentation ↗</a>` +
                  pretty(m);
                $("#detail").showModal();
              })),
        );
    };
    render("");
    $("#search-method").oninput = (e) => render(e.target.value);
  },
  async automations() {
    const ws = await api("workflows");
    content.innerHTML =
      `<div class="card"><h2>Durable workflows</h2><p>Compose a fixed sequence, a one-time or cron trigger, and an execution limit. Owner approval authorizes exactly this plan.</p><textarea id="workflow-json" rows="14"></textarea><div class="actions"><button id="workflow-create" class="primary">Create workflow draft</button></div></div>` +
      table(
        ["Name", "Active", "Runs", "Next run", "Actions"],
        ws.map(
          (w) =>
            `<tr><td>${esc(w.name)}</td><td>${w.active ? "Active" : "Paused / draft"}</td><td>${w.runs_count}/${w.max_runs}</td><td>${esc(w.next_run || "Event trigger")}</td><td><button data-w="${w.id}">Inspect</button></td></tr>`,
        ),
      );
    $("#workflow-json").value = JSON.stringify(
      {
        name: "Publish and pin",
        timezone: "Asia/Tehran",
        max_runs: 1,
        trigger: {
          type: "once",
          at: new Date(Date.now() + 3600000).toISOString(),
        },
        steps: [
          {
            method: "sendMessage",
            payload: { chat_id: "@your_channel", text: "Approved content" },
          },
          {
            method: "pinChatMessage",
            payload: {
              chat_id: "@your_channel",
              message_id: "$steps.0.result.message_id",
            },
          },
          {
            delay_seconds: 86400,
            method: "unpinChatMessage",
            payload: {
              chat_id: "@your_channel",
              message_id: "$steps.0.result.message_id",
            },
          },
        ],
      },
      null,
      2,
    );
    $("#workflow-create").onclick = () =>
      act(async () => {
        await api("workflows", "POST", JSON.parse($("#workflow-json").value));
        notice("Workflow draft created.");
        await load();
      });
    content.querySelectorAll("[data-w]").forEach(
      (b) =>
        (b.onclick = () =>
          act(async () => {
            const w = ws.find((w) => w.id === b.dataset.w);
            const box = $("#detail-body");
            box.innerHTML = pretty(w);
            if (role === "owner")
              box.prepend(
                btn(
                  "Approve / enable",
                  async () => {
                    await api("workflows/" + w.id + "/approve", "POST", {
                      expected_digest: w.digest,
                    });
                    $("#detail").close();
                    await load();
                  },
                  "primary",
                ),
              );
            box.prepend(
              btn("Pause", async () => {
                await api("workflows/" + w.id + "/pause", "POST");
                $("#detail").close();
                await load();
              }),
            );
            $("#detail").showModal();
          })),
    );
  },
  async emojis() {
    const es = await api(
      "emojis?" +
        new URLSearchParams({
          limit: 40,
          offset: emojiOffset,
          q: emojiQuery,
          pack: emojiPack,
        }),
    );
    content.innerHTML = `<div class="card"><h2>Choose by appearance, keep a consistent style</h2><p>Import a custom emoji pack with getStickerSet. Generate a preview, inspect the actual image, then add descriptions and roles.</p><div class="actions"><input id="pack-name" placeholder="Pack name, e.g. FinanceEmoji" style="max-width:300px"><button id="import-pack">Import pack</button></div></div><div class="card"><div class="actions"><input id="emoji-search" placeholder="Search ID, description or tags" value="${esc(emojiQuery)}"><input id="emoji-pack-filter" placeholder="Filter by pack name" value="${esc(emojiPack)}"><button id="emoji-filter">Search</button></div><div class="actions"><button id="emoji-prev">Previous</button><span>Items ${emojiOffset + 1}–${emojiOffset + es.length}</span><button id="emoji-next">Next</button></div></div><div class="emoji-grid" id="emoji-grid"></div>`;
    $("#import-pack").onclick = () =>
      act(async () => {
        await api("operations", "POST", {
          method: "getStickerSet",
          payload: { name: $("#pack-name").value },
          idempotency_key: crypto.randomUUID(),
        });
        notice("Import queued. Refresh after the worker completes it.");
      });
    $("#emoji-prev").disabled = emojiOffset === 0;
    $("#emoji-next").disabled = es.length < 40;
    $("#emoji-prev").onclick = () =>
      act(async () => {
        emojiOffset = Math.max(0, emojiOffset - 40);
        await load();
      });
    $("#emoji-next").onclick = () =>
      act(async () => {
        emojiOffset += 40;
        await load();
      });
    $("#emoji-filter").onclick = () =>
      act(async () => {
        emojiQuery = $("#emoji-search").value;
        emojiPack = $("#emoji-pack-filter").value;
        emojiOffset = 0;
        await load();
      });
    const g = $("#emoji-grid");
    for (const e of es) {
      const card = document.createElement("div");
      card.className = "emoji";
      card.innerHTML = `<div class="label">${esc(e.pack)}</div><div class="stat">${esc(e.alt)}</div><code>${esc(e.id)}</code><p>${esc(e.labels.description || "Not labeled")}</p>${status(e.reviewed ? "succeeded" : "draft")}`;
      if (e.preview_id) {
        const r = await fetch("/v1/assets/" + e.preview_id, {
          headers: { Authorization: "Bearer " + key },
        });
        const u = URL.createObjectURL(await r.blob());
        const im = new Image();
        im.src = u;
        im.onload = () => URL.revokeObjectURL(u);
        card.prepend(im);
      }
      card.append(
        btn("Preview", async () => {
          await api("emojis/" + e.id + "/preview", "POST");
          await load();
        }),
      );
      card.append(
        btn("Label & review", async () => {
          const description = prompt(
            "Describe the image you inspected",
            e.labels.description || "",
          );
          if (description === null) return;
          await api("emojis/" + e.id, "PATCH", {
            description,
            tags: e.labels.tags || [],
            style: e.labels.style || "",
            reviewed: true,
          });
          await load();
        }),
      );
      if (e.reviewed)
        card.append(
          btn("Bind role", async () => {
            const name = prompt("Role name, e.g. primary_cta or warning");
            if (!name) return;
            await api("emoji-roles/" + encodeURIComponent(name), "PUT", {
              emoji_id: e.id,
            });
            notice("Emoji assigned to " + name);
          }),
        );
      g.append(card);
    }
  },
  async logs() {
    const logs = await api("logs?limit=200");
    content.innerHTML = table(
      ["Time", "Actor", "Action", "Resource", "Details"],
      logs
        .reverse()
        .map(
          (l) =>
            `<tr><td>${esc(new Date(l.at).toLocaleString())}</td><td>${esc(l.actor)}</td><td>${esc(l.action)}</td><td><code>${esc(l.resource_id)}</code></td><td>${esc(JSON.stringify(l.details))}</td></tr>`,
        ),
    );
  },
  async database() {
    const d = await api("database/overview");
    content.innerHTML =
      '<div class="card"><h2>Persistent system records</h2><p>Inspect schema and counts through the API. Operations, workflows, audit, updates and emoji each have dedicated read endpoints.</p></div>' +
      table(
        ["Table", "Rows", "Columns"],
        d.tables.map(
          (t) =>
            `<tr><td><b>${esc(t.name)}</b></td><td>${t.rows}</td><td>${esc(t.columns.map((c) => c.name).join(", "))}</td></tr>`,
        ),
      );
  },
};
