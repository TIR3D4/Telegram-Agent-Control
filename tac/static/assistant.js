"use strict";
titles.assistant = "دستیار Telegram";
let chatTimer;
const chatState = { current: null, parent: null };
const chatStatuses = {queued:"در صف", running:"در حال اجرا", succeeded:"پایان یافت", failed:"ناموفق", interrupted:"متوقف شد؛ دوباره اجرا نشده", cancelled:"لغو شد", draft:"منتظر تأیید مالک", completed:"تکمیل ابزار"};
function renderTurn(t) {
  const card = document.createElement("article");
  card.className = "chat-turn card";
  card.dataset.turn = t.id;
  const operations = (t.events || []).filter(e => e.operation_id);
  card.innerHTML = `<p class="chat-user">${esc(t.text)}</p><p class="chat-state" role="status">${esc(chatStatuses[t.status] || t.status)}</p>
    <div class="chat-events">${(t.events||[]).map(e=>`<p dir="auto">${esc(e.tool)} · ${esc(chatStatuses[e.status]||e.status)}</p>`).join("")}</div>
    <p class="chat-reply">${esc(t.reply||"")}</p>${t.error?`<p class="error" dir="auto">${esc(t.error)}</p>`:""}
    <p class="muted">${esc(t.usage?.total_tokens||0)} توکن · ${esc(t.usage?.calls||0)} درخواست مدل</p>`;
  for (const event of operations) {
    card.append(btn("بررسی عملیات و تأیید مستقل مالک", () => showOperation(event.operation_id), "primary"));
  }
  if (["queued","running"].includes(t.status)) card.append(btn("توقف گفتگو", async()=>{
    await api(`assistant/turns/${t.id}/cancel`,"POST"); await pollTurn(t.id);
  }));
  return card;
}
async function pollTurn(id) {
  clearTimeout(chatTimer);
  if (view !== "assistant" || (!csrf && !key)) return;
  const t = await api(`assistant/turns/${id}`);
  const old = document.querySelector(`[data-turn="${id}"]`);
  if (old) old.replaceWith(renderTurn(t));
  if (["queued","running"].includes(t.status)) chatTimer=setTimeout(()=>act(()=>pollTurn(id)),1500);
  else { chatState.current=null; if(t.status==="succeeded") chatState.parent=t.id; }
  const send = $("#chat-send"); if(send) send.disabled=!!chatState.current||paused;
}
pages.assistant = async () => {
  clearTimeout(chatTimer);
  if(role!=="owner") {content.innerHTML='<p class="card" dir="rtl">ورود مستقل مالک لازم است.</p>';return;}
  const [c, turns, system] = await Promise.all([api("assistant/config"),api("assistant/turns"),api("system")]);
  paused=!!system.paused.enabled;
  content.innerHTML=`<section class="assistant" dir="rtl" lang="fa">
    ${paused?`<section class="card"><p>اجرای سرور متوقف است. ابتدا عملیات قبلی و نتیجهٔ ارتقا را بررسی کنید؛ گفتگو در حالت توقف اجرا نمی‌شود.</p><button id="chat-resume">ادامهٔ اجرا پس از بررسی مالک</button></section>`:""}
    <p class="card">با دستیار گفتگو کنید. ارسال و تغییر Telegram فقط بعد از بررسی و تأیید شما انجام می‌شود.</p>
    <details class="card" ${c.configured?"":"open"}><summary>تنظیم مدل و ارائه‌دهنده</summary>
      <p>${esc(c.cost_notice)}</p><p>کلید را فقط در این فرم وارد کنید؛ آن را در گفتگو ننویسید. کلید ذخیره‌شده نمایش داده نمی‌شود.</p>
      <form id="chat-config"><label>ارائه‌دهنده<select id="chat-provider"><option value="openai">OpenAI</option><option value="openrouter">OpenRouter</option><option value="groq">Groq</option></select></label>
      <label>شناسهٔ مدل<input dir="ltr" id="chat-model" required maxlength="120" value="${esc(c.model)}" placeholder="شناسهٔ دقیق مدل در حساب ارائه‌دهنده"></label>
      <label>کلید API<input type="password" id="chat-key" autocomplete="new-password" placeholder="خالی: حفظ کلید فعلی"></label>
      <label>کانال‌های مجاز<input dir="ltr" id="chat-channels" placeholder="@channel"></label>
      <label><input type="checkbox" id="chat-replace"> ایجاد مجوز جدید ۳۰روزه و لغو مجوز قبلی</label>
      <button class="primary">ذخیرهٔ امن تنظیمات</button></form>
      <button type="button" id="chat-test">تست اتصال فقط‌خواندنی Telegram</button>
      <p>مجوز: ${esc(c.grant_id||"هنوز ایجاد نشده")} · سقف ۱۰۰ عملیات در روز. محدودیت هزینه را در حساب ارائه‌دهنده تنظیم کنید.</p>
    </details>
    <div id="chat-history" aria-live="polite"></div>
    <form id="chat-form" class="card"><label for="chat-text">درخواست شما</label><textarea id="chat-text" rows="3" maxlength="8000" required placeholder="سلامت ربات را بررسی کن"></textarea>
      <div class="actions"><button id="chat-send" class="primary" ${c.configured?"":"disabled"}>ارسال</button><button type="button" id="chat-new">گفتگوی تازه</button></div>
    </form><details class="card"><summary>توسعه و ارتقا</summary><p>درخواست توسعه در اینجا به پیشنهاد تبدیل می‌شود. اجرای کد در شاخه و محیط جدا و تأیید PR انجام می‌شود. این دستیار دسترسی root یا استقرار ندارد.</p><a href="https://github.com/TIR3D4/Telegram-Agent-Control/pulls" target="_blank" rel="noopener">بررسی تغییرات GitHub</a><div id="chat-proposals"></div></details>
  </section>`;
  $("#chat-provider").value=c.provider;
  $("#chat-test").onclick=()=>act(async()=>{const o=await api("assistant/connection-test","POST");if(o.error)throw Error(o.detail||o.error);await showOperation(o.id);});
  const history=$("#chat-history");
  for(const t of [...turns].reverse()) history.append(renderTurn(t));
  chatState.current=turns.find(t=>["queued","running"].includes(t.status))?.id||null;
  chatState.parent=turns.find(t=>t.status==="succeeded")?.id||null;
  $("#chat-send").disabled=!!chatState.current||!c.configured||paused;
  if($("#chat-resume")) $("#chat-resume").onclick=()=>act(async()=>{if(!confirm("پس از بررسی عملیات صف، اجرای سرور را ادامه می‌دهید؟"))return;await api("system/pause?enabled=false","POST");await pages.assistant();});
  $("#chat-config").onsubmit=e=>{e.preventDefault();act(async()=>{
    const secret=$("#chat-key").value; $("#chat-key").value="";
    await api("assistant/config","PUT",{provider:$("#chat-provider").value,model:$("#chat-model").value,
      ...(secret?{api_key:secret}:{}),channels:$("#chat-channels").value.split(",").map(s=>s.trim()).filter(Boolean),replace_grant:$("#chat-replace").checked});
    notice("تنظیمات ذخیره شد. کلید فقط روی سرور نگهداری می‌شود.");await pages.assistant();
  });};
  $("#chat-form").onsubmit=e=>{e.preventDefault();act(async()=>{
    $("#chat-send").disabled=true;
    const t=await api("assistant/turns","POST",{text:$("#chat-text").value,idempotency_key:crypto.randomUUID(),parent_id:chatState.parent});
    $("#chat-text").value="";chatState.current=t.id;history.append(renderTurn(t));await pollTurn(t.id);
  }).finally(()=>{if(!chatState.current && $("#chat-send")) $("#chat-send").disabled=false;});};
  $("#chat-new").onclick=()=>{chatState.parent=null;notice("درخواست بعدی بدون سابقهٔ گفتگو ارسال می‌شود.");};
  const proposals=await api("assistant/development-proposals");
  $("#chat-proposals").innerHTML=proposals.map(p=>`<article><h3>${esc(p.title)}</h3><p class="chat-reply">${esc(p.description)}</p></article>`).join("");
  if(chatState.current) await pollTurn(chatState.current);
};

$("#chat-nav-toggle").onclick=()=>{const open=document.querySelector("aside").classList.toggle("chat-nav-open");$("#chat-nav-toggle").setAttribute("aria-expanded",String(open));};
