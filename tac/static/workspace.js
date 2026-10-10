"use strict";
// UI adapters use the existing authenticated REST services; no publishing authority here.
Object.assign(titles, {overview:"مرکز کنترل", connections:"اتصال دستیارها", compose:"ساخت پست", operations:"پست‌ها و عملیات", automations:"زمان‌بندی و اتوماسیون", emojis:"استودیوی ایموجی", methods:"مرجع API", logs:"رویدادها", database:"پایگاه داده", channels:"کانال‌ها", media:"رسانه‌ها", keyboards:"دکمه‌ها", agents:"مجوز دستیارها", diagnostics:"سلامت سرویس", settings:"تنظیمات", maintenance:"تأییدهای مدیریتی"});
for (const el of document.querySelectorAll("nav button[data-view]")) {
  if (el.dataset.view !== "assistant") el.textContent = titles[el.dataset.view];
}
$("#refresh").textContent="بروزرسانی";
$("#disconnect").textContent="خروج";
$("#close-detail").textContent="بستن";
$(".eyebrow").textContent="TELEGRAM / CONTROL WORKSPACE";
$("#title").textContent=titles.overview;

function navigate(next) { view=next; return act(load); }
function wireNavigation() {
  content.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>navigate(b.dataset.go));
}
function downloadText(name, value) {
  const url=URL.createObjectURL(new Blob([value],{type:"text/plain;charset=utf-8"}));
  const a=document.createElement('a');a.href=url;a.download=name;a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}

pages.overview=async()=>{
  const [s,m]=await Promise.all([api('system'),api('metrics')]);
  paused=!!s.paused.enabled;
  $('#pause').textContent=paused?'ادامهٔ اجرا':'توقف اجرا';$('#pause').disabled=role!=='owner';
  content.innerHTML=`<section class="hero workspace-hero"><div><span class="tag">مرکز فرمان Telegram</span><h2>کنترل Telegram،<br>کنار دستیار شما.</h2><p>اتصال‌ها، پست‌ها و زمان‌بندی‌ها در یک فضای کاری.</p><div class="actions"><button class="primary" data-go="connections">اتصال دستیار</button><button data-go="compose">ساخت پست</button></div></div><div class="hero-health"><span class="health-dot ${m.worker_healthy?'online':''}"></span><strong>${m.worker_healthy?'پردازشگر فعال':'پردازشگر نیاز به بررسی دارد'}</strong><p>${paused?'اجرا متوقف است':'صف آمادهٔ اجراست'}</p><small>${s.methods} methods · Bot API ${esc(s.api_version)}</small></div></section>
  <div class="grid metrics-grid">${[['در انتظار تأیید',s.operations.draft||0],['در صف',s.operations.queued||0],['ارسال موفق',s.operations.succeeded||0],['نیازمند بررسی',(s.operations.failed||0)+(s.operations.uncertain||0)]].map(([label,n])=>`<div class="card metric"><span>${label}</span><strong>${n}</strong></div>`).join('')}</div>
  <div class="split"><section class="card"><h2>مسیر کار روزانه</h2><ol class="steps"><li>در ChatGPT، Codex یا Claude درخواست بده.</li><li>دستیار متن، رسانه و زمان را آماده می‌کند.</li><li>نسخهٔ دقیق را در پنل تأیید کن.</li><li>نتیجه و لینک پیام را در همان گفتگو بگیر.</li></ol><button data-go="operations">بررسی پست‌ها</button></section><section class="card"><h2>فضای کاری شما</h2><p>ربات: ${s.bot_configured?'تنظیم شده':'نیازمند تنظیم'}</p><p>کانال‌های مجاز</p><p dir="ltr">${esc(s.allowed_chats.join(' · ')||'—')}</p><div class="actions"><button data-go="agents">مدیریت دسترسی</button><button data-go="diagnostics">سلامت و خطاها</button></div><p class="help">پیکربندی ربات به‌تنهایی تأیید اتصال Telegram نیست.</p></section></div>`;
  wireNavigation();
};

const legacyConnections=pages.connections;
pages.connections=async()=>{
  if(role!=='owner'){content.innerHTML='<section class="card">ورود مالک لازم است.</section>';return;}
  const c=await api('connections');
  content.innerHTML=`<section class="connection-intro"><span class="tag">CONNECT YOUR AI</span><h2>یک مرکز؛ دستیار دلخواه شما.</h2><p>روش اتصال را انتخاب کن، مجوز محدود بساز و اتصال واقعی را آزمایش کن.</p></section><div class="connection-tabs" role="tablist" aria-label="روش اتصال">${c.profiles.map((p,i)=>`<button role="tab" aria-selected="${i===0}" data-profile="${p.id}">${esc(p.title)}</button>`).join('')}</div><section id="connection-profile" class="card"></section>
  <section class="card"><h2>آزمایش واقعی از مرورگر شما</h2><p>کلید محدود دستیار را وارد کنید. تست، هویت REST و آغاز پروتکل MCP و فهرست ابزارها را بررسی می‌کند؛ هیچ پیامی ارسال نمی‌شود. نتیجه فقط مسیر شبکهٔ همین مرورگر را تأیید می‌کند.</p><label for="connection-test-token">کلید محدود دستیار</label><input id="connection-test-token" type="password" autocomplete="off"><button id="connection-test" class="primary">بررسی REST و MCP</button><div id="connection-evidence" aria-live="polite"></div></section>
  <section class="card"><h2>دسترسی و رسانه</h2><p>برای هر دستیار مجوز جدا، کانال مشخص و تاریخ انقضا تعریف کنید. کلید مالک را در دستیار قرار ندهید.</p><div class="actions"><button id="new-api-key" data-go="agents">ساخت و مدیریت مجوز</button><button data-go="media">مدیریت رسانه‌ها</button><button id="advanced-connections">تنظیم OAuth و اتصال ثبت‌شده</button></div><p class="help">رسانه: آپلود فایل با REST؛ انتقال Base64 تا ۱ MiB با MCP. دسترسی به فایل ساخته‌شده به قابلیت محیط دستیار بستگی دارد؛ مسیر sandbox لینک دانلود نیست.</p></section>`;
  function select(id){
    const p=c.profiles.find(x=>x.id===id);
    content.querySelectorAll('[data-profile]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.profile===id)));
    $('#connection-profile').innerHTML=`<div class="connection-heading"><div><h2>${esc(p.title)}</h2><p>${esc(p.subtitle)}</p></div><span class="badge">${esc(p.auth)}</span></div><label for="connection-url">آدرس اتصال</label><div class="copy-row"><input dir="ltr" id="connection-url" readonly value="${esc(p.endpoint)}"><button id="copy-url">کپی آدرس</button></div><ol class="steps">${p.steps.map(x=>`<li>${esc(x)}</li>`).join('')}</ol><div class="connection-limit">${esc(p.limitation)}</div><details><summary>تنظیم آماده و راهنمای دستیار</summary><pre dir="ltr">${esc(p.config)}</pre><button id="download-profile">دریافت تنظیمات بدون کلید</button><label for="agent-instruction">متن راهنمای دستیار</label><textarea id="agent-instruction" dir="ltr" readonly rows="4"></textarea></details>`;
    $('#agent-instruction').value=`Use ${c.agent_guide_url}. Inspect identity and capabilities first. Keep the scoped credential in your host secret store. Upload actual file bytes through ${c.media.multipart} or upload_media; never invent download URLs. Prepare drafts with stable idempotency keys, return the owner review link, poll delivery; do not approve yourself or retry uncertain sends.`;
    $('#copy-url').onclick=()=>act(async()=>{await navigator.clipboard.writeText(p.endpoint);notice('آدرس کپی شد');});
    $('#download-profile').onclick=()=>downloadText(p.filename,p.config);
  }
  select('api');
  content.querySelectorAll('[data-profile]').forEach(b=>b.onclick=()=>select(b.dataset.profile));
  wireNavigation();
  $('#advanced-connections').onclick=()=>act(legacyConnections);
  $('#connection-test').onclick=()=>act(async()=>{
    const token=$('#connection-test-token').value.trim();$('#connection-test-token').value='';
    if(!token)throw Error('کلید محدود دستیار را وارد کنید.');
    const button=$('#connection-test');button.disabled=true;
    const evidence=$('#connection-evidence');evidence.textContent='در حال بررسی…';
    try{
      const headers={Authorization:'Bearer '+token,'Content-Type':'application/json',Accept:'application/json, text/event-stream'};
      async function request(path,body){
        const r=await fetch(path,{method:body?'POST':'GET',headers,credentials:'omit',redirect:'error',signal:AbortSignal.timeout(20000),body:body?JSON.stringify(body):undefined});
        if(!r.ok)throw Error(`HTTP ${r.status} — کلید، مجوز یا مسیر اتصال را بررسی کنید.`);
        const data=await r.json();if(data.error)throw Error('MCP پاسخ خطا داد.');return data;
      }
      const system=await request('/v1/system');
      if(system.role==='owner')throw Error('کلید مالک پذیرفته نیست؛ مجوز محدود دستیار بسازید.');
      const init=await request('/mcp/',{jsonrpc:'2.0',id:1,method:'initialize',params:{protocolVersion:'2025-06-18',capabilities:{},clientInfo:{name:'tac-console-check',version:'0.4'}}});
      if(!init.result?.protocolVersion)throw Error('پاسخ initialize معتبر نیست.');
      const list=await request('/mcp/',{jsonrpc:'2.0',id:2,method:'tools/list',params:{}});
      if(!Array.isArray(list.result?.tools))throw Error('فهرست ابزارها دریافت نشد.');
      evidence.textContent=`REST تأیید شد · MCP ${init.result.protocolVersion} · ${list.result.tools.length} ابزار · هویت ${system.identity} · ${new Date().toLocaleString('fa-IR')}. اتصال از خود دستیار هنوز باید در همان دستیار آزمایش شود.`;
    }catch(e){evidence.textContent='اتصال تأیید نشد: '+e.message;throw e;}finally{button.disabled=false;}
  });
};

// Everyday composition is a visual form; exact Telegram JSON remains an explicit advanced mode.
const advancedCompose=pages.compose;
pages.compose=async()=>{
  const s=await api('system');
  let asset=null, objectURL=null, pending=false, savedId=null;
  const requestKey=crypto.randomUUID();
  content.innerHTML=`<div class="split composer"><section class="card"><h2>پست جدید</h2><form id="post-form"><label for="post-channel">کانال</label><select id="post-channel" required>${s.allowed_chats.map(c=>`<option>${esc(c)}</option>`).join('')}</select><label for="post-text">متن یا کپشن</label><textarea id="post-text" rows="6" required placeholder="متن پست را بنویسید…"></textarea><label for="post-file">تصویر (اختیاری)</label><input id="post-file" type="file" accept="image/png,image/jpeg,image/webp"><div id="post-upload-status" role="status"></div><label for="post-time">زمان ارسال — منطقهٔ زمانی مرورگر: ${esc(Intl.DateTimeFormat().resolvedOptions().timeZone)}</label><input id="post-time" type="datetime-local"><fieldset><legend>دکمه‌های زیر پست (اختیاری)</legend>${[1,2].map(n=>`<div class="form-grid"><label>متن دکمه ${n}<input id="post-button-${n}" maxlength="100"></label><label>لینک دکمه ${n}<input id="post-url-${n}" type="url" dir="ltr" placeholder="https://t.me/…"></label></div>`).join('')}</fieldset><button id="post-save" class="primary">ذخیره و بررسی برای تأیید</button></form><button id="advanced-compose">ویرایش پیشرفتهٔ JSON و سایر روش‌ها</button></section><section class="card preview-card"><h2>پیش‌نمایش پست</h2><div class="telegram-preview"><img id="visual-post-image" alt="پیش‌نمایش تصویر" hidden><div id="visual-post-text"></div><div id="visual-post-buttons"></div></div><p class="help">نمای تقریبی؛ ظاهر نهایی را Telegram تعیین می‌کند. ذخیرهٔ پیش‌نویس به معنی ارسال نیست.</p></section></div>`;
  const render=()=>{
    $('#visual-post-text').textContent=$('#post-text').value||'متن پست شما اینجا نمایش داده می‌شود.';
    $('#visual-post-buttons').innerHTML=[1,2].filter(n=>$('#post-button-'+n).value).map(n=>`<span>${esc($('#post-button-'+n).value)}</span>`).join('');
  };
  $('#post-form').oninput=render;render();
  $('#advanced-compose').onclick=()=>act(advancedCompose);
  $('#post-file').onchange=()=>act(async()=>{
    const file=$('#post-file').files[0];asset=null;
    if(objectURL)URL.revokeObjectURL(objectURL);
    $('#visual-post-image').hidden=true;
    if(!file)return;
    pending=true;$('#post-file').disabled=true;$('#post-save').disabled=true;$('#post-upload-status').textContent='در حال بارگذاری…';
    try{
      const form=new FormData();form.append('file',file);asset=await api('assets','POST',form);
      objectURL=URL.createObjectURL(file);$('#visual-post-image').src=objectURL;$('#visual-post-image').hidden=false;
      $('#post-upload-status').textContent='تصویر آماده است';
    }catch(e){$('#post-upload-status').textContent='آپلود ناموفق؛ دوباره فایل را انتخاب کنید.';throw e;}
    finally{pending=false;$('#post-file').disabled=false;$('#post-save').disabled=false;}
  });
  $('#post-form').onsubmit=e=>{e.preventDefault();act(async()=>{
    if(savedId){await showOperation(savedId);return;}
    if(pending)throw Error('تا پایان آپلود صبر کنید.');
    if($('#post-file').files.length&&!asset)throw Error('تصویر بارگذاری نشده است.');
    $('#post-save').disabled=true;
    try{
      const payload={chat_id:$('#post-channel').value,[asset?'caption':'text']:$('#post-text').value};
      if(asset)payload.photo='attach://photo';
      const buttons=[1,2].filter(n=>$('#post-button-'+n).value).map(n=>({text:$('#post-button-'+n).value,url:$('#post-url-'+n).value}));
      if(buttons.length){const keyboard=await api('keyboards/build','POST',{rows:[buttons]});payload.reply_markup=keyboard.reply_markup;}
      const method=asset?'sendPhoto':'sendMessage';
      await api('validate','POST',{method,payload});
      const o=await api('operations','POST',{method,payload,attachments:asset?{photo:asset.id}:{},run_at:$('#post-time').value?new Date($('#post-time').value).toISOString():null,idempotency_key:requestKey});
      savedId=o.id;notice('پیش‌نویس ذخیره شد؛ نسخهٔ دقیق را بررسی کنید.');await showOperation(o.id);
      $('#post-save').textContent='مشاهدهٔ پیش‌نویس ذخیره‌شده';
      $('#post-form').querySelectorAll('input,textarea,select').forEach(el=>el.disabled=true);
      $('#post-form').append(btn('ساخت پست دیگری',pages.compose));
    }finally{$('#post-save').disabled=false;}
  });};
};

let operationFilter='', operationBefore=null;
pages.operations=async()=>{
  const query=new URLSearchParams({limit:30});if(operationFilter)query.set('status',operationFilter);if(operationBefore)query.set('before',operationBefore);
  const ops=await api('operations?'+query);
  const labels={draft:'در انتظار تأیید',queued:'در صف',running:'در حال اجرا',succeeded:'موفق',failed:'ناموفق',uncertain:'نتیجه نامشخص',cancelled:'لغوشده'};
  content.innerHTML=`<section class="card operation-toolbar"><div><h2>پست‌ها و عملیات</h2><p>نسخهٔ دقیق، زمان اجرا و وضعیت ارسال را بررسی کنید.</p></div><label for="operation-filter">وضعیت<select id="operation-filter"><option value="">همهٔ وضعیت‌ها</option>${Object.entries(labels).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></label><button data-go="compose" class="primary">پست جدید</button></section><div class="operation-list">${ops.map(o=>`<article class="card operation-card"><div class="operation-meta"><span class="badge ${esc(o.status)}">${esc(labels[o.status]||o.status)}</span><span dir="ltr">${esc(o.method)}</span></div><h3 dir="auto">${esc(o.payload.chat_id||'بررسی بدون مقصد کانال')}</h3><p class="operation-excerpt" dir="auto">${esc((o.payload.text||o.payload.caption||'رسانه یا عملیات بدون متن').slice(0,220))}</p><small>زمان اجرا: ${esc(new Date(o.run_at).toLocaleString('fa-IR'))} · ${o.attempts} تلاش</small><div class="actions"><button data-id="${o.id}">${o.status==='draft'?'بررسی و تأیید':'مشاهدهٔ نتیجه'}</button></div></article>`).join('')||'<section class="card empty">عملیاتی در این بخش وجود ندارد.</section>'}</div><div class="actions"><button id="operations-first" ${operationBefore?'':'disabled'}>جدیدترین</button><button id="operations-next" ${ops.length===30?'':'disabled'}>قدیمی‌تر</button></div>`;
  $('#operation-filter').value=operationFilter;
  $('#operation-filter').onchange=()=>{operationFilter=$('#operation-filter').value;operationBefore=null;act(pages.operations);};
  $('#operations-next').onclick=()=>{operationBefore=ops[ops.length-1].created_at;act(pages.operations);};
  $('#operations-first').onclick=()=>{operationBefore=null;act(pages.operations);};
  content.querySelectorAll('[data-id]').forEach(b=>b.onclick=()=>act(()=>showOperation(b.dataset.id)));wireNavigation();
};
