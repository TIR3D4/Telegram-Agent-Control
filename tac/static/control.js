"use strict";
Object.assign(titles, {
  agents: "Agent permissions",
  media: "Media library",
  keyboards: "Inline keyboards",
  channels: "Telegram channels",
  diagnostics: "Health & metrics",
  settings: "Settings",
  maintenance: "Maintenance approvals",
});
Object.assign(pages, {
  async agents() {
    if (role !== "owner") {
      content.innerHTML =
        '<div class="card"><h2>Owner access required</h2><p>Agents cannot create credentials or expand their own permissions.</p></div>';
      return;
    }
    const grants = await api("agents");
    const system = await api("system");
    content.innerHTML =
      `<div class="card"><h2>Issue a scoped agent credential</h2><p>Grant only the channels, actions and lifetime this agent needs. Approval remains with the human owner.</p><div class="form-grid"><div><label for="grant-name">Name</label><input id="grant-name" maxlength="120" placeholder="Content assistant"></div><div><label for="grant-role">Preset</label><select id="grant-role"><option>OPERATE</option><option>READ</option><option>ADMIN</option></select></div><div><label for="grant-chats">Allowed channels (comma separated)</label><input id="grant-chats" value="${esc(system.allowed_chats.join(","))}"></div><div><label for="grant-expiry">Expires in days (1–365)</label><input id="grant-expiry" type="number" min="1" max="365" value="30"></div><div><label for="grant-rpm">Requests per minute</label><input id="grant-rpm" type="number" min="1" max="1000" value="120"></div><div><label for="grant-daily">Operations per day</label><input id="grant-daily" type="number" min="1" max="10000" value="100"></div></div><label for="grant-subject">OAuth subject (optional; binds an identity-provider subject)</label><input id="grant-subject" autocomplete="off"><label for="grant-methods">Exact method allowlist (optional comma list; blank uses preset)</label><input id="grant-methods" placeholder="getMe,getChat,getChatMember,sendMessage,sendPhoto"><label for="grant-scopes">Scopes (optional comma list; blank uses preset)</label><input id="grant-scopes" placeholder="system:read,posts:read,posts:write"><div class="actions"><button id="grant-create" class="primary">Review and create credential</button></div></div>` +
      table(
        ["Agent", "Preset", "Expiry", "Status", "Controls"],
        grants.map(
          (g) =>
            `<tr><td>${esc(g.name)}<br><code>${esc(g.id)}</code></td><td>${esc(g.preset)}</td><td>${esc(new Date(g.expires_at).toLocaleString())}</td><td>${status(g.revoked_at ? "revoked" : new Date(g.expires_at) < new Date() ? "expired" : "active")}</td><td><button data-grant="${g.id}">Inspect policy</button><button data-revoke="${g.id}" class="danger">Request revocation</button><button data-rotate="${g.id}">Request rotation</button></td></tr>`,
        ),
      );
    $("#grant-create").onclick = () =>
      act(async () => {
        const body = {
          name: $("#grant-name").value,
          preset: $("#grant-role").value,
          chats: $("#grant-chats")
            .value.split(",")
            .map((s) => s.trim())
            .filter(Boolean),
          expires_at: new Date(
            Date.now() + Number($("#grant-expiry").value) * 86400000,
          ).toISOString(),
          rpm: Number($("#grant-rpm").value),
          daily_operations: Number($("#grant-daily").value),
        };
        if ($("#grant-subject").value)
          body.oauth_subject = $("#grant-subject").value;
        for (const f of ["methods", "scopes"])
          if ($("#grant-" + f).value)
            body[f] = $("#grant-" + f)
              .value.split(",")
              .map((s) => s.trim())
              .filter(Boolean);
        const box = $("#detail-body");
        box.innerHTML = "<h3>Review the exact grant</h3>" + pretty(body);
        box.append(
          btn(
            "Create this grant",
            async () => {
              const out = await api("agents", "POST", body);
              box.innerHTML =
                "<h3>Credential created</h3><p>Save the credential privately now. It is not stored in recoverable form.</p>" +
                pretty(out);
              await load();
            },
            "primary",
          ),
        );
        $("#detail").showModal();
      });
    content.querySelectorAll("[data-grant]").forEach(
      (b) =>
        (b.onclick = () => {
          showJSON(
            "Agent policy",
            grants.find((g) => g.id === b.dataset.grant),
          );
        }),
    );
    content
      .querySelectorAll("[data-revoke]")
      .forEach(
        (b) =>
          (b.onclick = () =>
            act(() =>
              requestChange("revoke_credential", {
                agent_id: b.dataset.revoke,
              }),
            )),
      );
    content
      .querySelectorAll("[data-rotate]")
      .forEach(
        (b) =>
          (b.onclick = () =>
            act(() =>
              requestChange("rotate_credential", {
                agent_id: b.dataset.rotate,
              }),
            )),
      );
  },
  async media() {
    const assets = await api("assets?limit=100");
    content.innerHTML =
      '<div class="card"><h2>Reusable media</h2><p>Assets are immutable. Referenced files cannot be deleted. Larger uploads use multipart transfer.</p><label for="library-upload">Upload a file</label><input type="file" id="library-upload"></div>' +
      table(
        ["File", "Type / size", "Asset ID", "Actions"],
        assets.map(
          (a) =>
            `<tr><td>${esc(a.name)}</td><td>${esc(a.mime)}<br>${(a.size / 1024).toFixed(1)} KB</td><td><code>${esc(a.id)}</code></td><td><button data-download="${a.id}">Download</button><button data-remove="${a.id}" class="danger">Request deletion</button></td></tr>`,
        ),
      );
    $("#library-upload").onchange = () =>
      act(async () => {
        const f = $("#library-upload").files[0];
        if (!f) return;
        const form = new FormData();
        form.append("file", f);
        await api("assets", "POST", form);
        notice("File uploaded.");
        await load();
      });
    content.querySelectorAll("[data-download]").forEach(
      (b) =>
        (b.onclick = () =>
          act(async () => {
            const r = await fetch("/v1/assets/" + b.dataset.download, {
              headers: { Authorization: "Bearer " + key },
            });
            if (!r.ok) throw Error("Download not authorized");
            const u = URL.createObjectURL(await r.blob());
            const a = document.createElement("a");
            a.href = u;
            a.download = assets.find((x) => x.id === b.dataset.download).name;
            a.click();
            setTimeout(() => URL.revokeObjectURL(u), 1000);
          })),
    );
    content
      .querySelectorAll("[data-remove]")
      .forEach(
        (b) =>
          (b.onclick = () =>
            act(() =>
              requestChange("delete_asset", { asset_id: b.dataset.remove }),
            )),
      );
  },
  async keyboards() {
    content.innerHTML = `<div class="card"><h2>Native Telegram buttons</h2><p>Build a compact two-button row. Use ordinary emoji in text, or an eligible custom emoji ID. Telegram decides client appearance.</p>${[1, 2].map((n) => `<fieldset><legend>Button ${n}</legend><div class="form-grid"><div><label for="button-text-${n}">Text (leave empty to omit)</label><input id="button-text-${n}" value="${n === 1 ? "🌐 Open" : "💬 Support"}"></div><div><label for="button-kind-${n}">Action</label><select id="button-kind-${n}"><option value="url">URL</option><option value="callback_data">Callback data</option></select></div><div><label for="button-value-${n}">URL / callback payload</label><input id="button-value-${n}" value="https://t.me"></div><div><label for="button-style-${n}">Official style</label><select id="button-style-${n}"><option value="">Default</option><option value="primary">Blue</option><option value="success">Green</option><option value="danger">Red</option></select></div><div><label for="button-emoji-${n}">Custom emoji ID (optional)</label><input id="button-emoji-${n}"></div></div></fieldset>`).join("")}<div class="actions"><button id="keyboard-build" class="primary">Validate and preview</button></div><div id="keyboard-result"></div></div>`;
    $("#keyboard-build").onclick = () =>
      act(async () => {
        const buttons = [1, 2]
          .filter((n) => $("#button-text-" + n).value)
          .map((n) => {
            const b = {
              text: $("#button-text-" + n).value,
              [$("#button-kind-" + n).value]: $("#button-value-" + n).value,
            };
            if ($("#button-style-" + n).value)
              b.style = $("#button-style-" + n).value;
            if ($("#button-emoji-" + n).value)
              b.icon_custom_emoji_id = $("#button-emoji-" + n).value;
            return b;
          });
        const r = await api("keyboards/build", "POST", {
          rows: buttons.length ? [buttons] : [],
        });
        $("#keyboard-result").innerHTML =
          "<h3>Validated reply_markup</h3>" +
          pretty(r.reply_markup) +
          "<p>" +
          esc(r.note) +
          "</p>";
        notice(
          "Use this reply_markup in your post or editMessageReplyMarkup operation.",
        );
      });
  },
  async channels() {
    const [accounts, channels] = await Promise.all([
      api("accounts"),
      api("channels"),
    ]);
    content.innerHTML =
      '<div class="card"><h2>Telegram connection</h2><p>This installation manages one Bot API account. Telegram permissions must be verified with getMe and getChatMember. Stored updates are available through the scoped agent API.</p>' +
      pretty(accounts) +
      "</div>" +
      table(
        ["Destination", "Permission evidence"],
        channels.items.map(
          (c) =>
            `<tr><td>${esc(c.chat_id)}</td><td>${esc(c.permission_status)}</td></tr>`,
        ),
      );
  },
  async diagnostics() {
    const [m, db] = await Promise.all([
      api("metrics"),
      api("database/overview"),
    ]);
    content.innerHTML = `<div class="grid"><div class="card"><div class="label">Worker</div>${status(m.worker_healthy ? "healthy" : "stale")}<p>Heartbeat age: ${m.worker_heartbeat_age_seconds === null ? "unknown" : Math.round(m.worker_heartbeat_age_seconds) + "s"}</p></div><div class="card"><div class="label">Oldest due item</div><div class="stat">${Math.round(m.oldest_due_age_seconds)}s</div></div><div class="card"><div class="label">Queue</div><div class="stat">${m.operations.queued || 0}</div></div><div class="card"><div class="label">Uncertain outcomes</div><div class="stat">${m.operations.uncertain || 0}</div></div></div><div class="card"><h2>Diagnostics</h2>${pretty(m)}</div><div class="card"><h2>Database</h2>${pretty(db)}</div>`;
  },
  async settings() {
    const s = await api("settings");
    content.innerHTML =
      '<div class="card"><h2>Safe configuration view</h2><p>Credentials and database connection strings are never returned. The server operator edits environment configuration locally and restarts services.</p>' +
      pretty(s) +
      "</div>";
  },
  async maintenance() {
    const rows = await api("admin/requests");
    content.innerHTML =
      '<div class="card"><h2>Independent human approval</h2><p>Requests bind exact parameters and expire after 15 minutes. Restore is executed by the local operator with a verified backup. Agents cannot approve or execute these changes.</p><label for="restore-name">Backup timestamp</label><input id="restore-name" placeholder="20261009T230000Z"><div class="actions"><button id="restore-request">Request restore review</button></div></div>' +
      table(
        ["Action", "State", "Expires", "Details"],
        rows.map(
          (r) =>
            `<tr><td>${esc(r.action)}</td><td>${status(r.status)}</td><td>${esc(new Date(r.expires_at).toLocaleString())}</td><td><button data-request="${r.id}">Review</button></td></tr>`,
        ),
      );
    $("#restore-request").onclick = () =>
      act(() =>
        requestChange("restore_backup", {
          backup_name: $("#restore-name").value,
        }),
      );
    content
      .querySelectorAll("[data-request]")
      .forEach(
        (b) =>
          (b.onclick = () =>
            showChange(rows.find((r) => r.id === b.dataset.request))),
      );
  },
});
function showJSON(title, value) {
  $("#detail-body").innerHTML = "<h3>" + esc(title) + "</h3>" + pretty(value);
  $("#detail").showModal();
}
async function requestChange(action, parameters) {
  const r = await api("admin/requests", "POST", { action, parameters });
  showChange(r);
}
function showChange(r) {
  const box = $("#detail-body");
  box.innerHTML = "<h3>Review maintenance request</h3>" + pretty(r);
  if (role === "owner" && r.status === "draft")
    box.append(
      btn(
        "Approve these exact parameters",
        async () => {
          const out = await api("admin/requests/" + r.id + "/approve", "POST", {
            expected_digest: r.digest,
          });
          showChange(out);
        },
        "primary",
      ),
    );
  if (role === "owner" && r.status === "approved")
    box.append(
      btn(
        "Execute approved request",
        async () => {
          const out = await api("admin/requests/" + r.id + "/execute", "POST");
          box.innerHTML = pretty(out);
          await load();
        },
        "danger",
      ),
    );
  $("#detail").showModal();
}
$("#close-detail").onclick = () => {
  $("#detail").close();
  $("#detail-body").replaceChildren();
};
