"use client";
import { useState, useEffect } from "react";
export default function Home() {
  const [connected, setConnected] = useState(false),
    [key, setKey] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("در حال بررسی اتصال…");
  useEffect(() => {
    fetch("/api/connection")
      .then((r) => r.json())
      .then((x: any) => {
        setConnected(!!x.connected);
        setMessage(
          x.error ||
            (x.connected
              ? "اتصال ذخیره شده است. به ChatGPT برگرد."
              : "یک‌بار دسترسی محدود سرور را متصل کن."),
        );
      })
      .catch(() => setMessage("امکان بررسی اتصال نیست. دوباره تلاش کن."));
  }, []);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await fetch("/api/connection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_key: key }),
      });
      const x = (await r.json()) as {
        error?: string;
        id?: string;
        connected?: boolean;
      };
      if (!r.ok) throw Error(x.error || "Request failed");
      setConnected(true);
      setMessage(
        "متصل شد. در ChatGPT افزونه را انتخاب کن و وضعیت ربات را بپرس.",
      );
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setKey("");
      setBusy(false);
    }
  }
  async function disconnect() {
    setBusy(true);
    try {
      const r = await fetch("/api/connection", { method: "DELETE" });
      if (!r.ok) throw Error("قطع اتصال انجام نشد");
      setConnected(false);
      setMessage(
        "دسترسی این رابط حذف شد. برای ابطال کامل کلید، از پنل سرور آن را لغو کن.",
      );
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function upload(file?: File) {
    if (!file) return;
    setBusy(true);
    try {
      const body = new FormData();
      body.set("file", file);
      const r = await fetch("/api/media", { method: "POST", body });
      const x = (await r.json()) as {
        error?: string;
        id?: string;
        connected?: boolean;
      };
      if (!r.ok) throw Error(x.error || "Request failed");
      setMessage(
        "تصویر ذخیره شد. به ChatGPT بگو از رسانه با شناسهٔ " +
          x.id +
          " استفاده کند.",
      );
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main dir="rtl" lang="fa" className="shell">
      <header>
        <span className="brand">AZAD BIRD / TELEGRAM CONTROL</span>
        <span className={"badge " + (connected ? "good" : "")}>
          {connected ? "دسترسی ذخیره شده" : "نیازمند اتصال"}
        </span>
      </header>
      <section>
        <div className="symbol">↗</div>
        <h1>
          گفتگو در ChatGPT.
          <br />
          اجرا در تلگرام.
        </h1>
        <p>
          این صفحه فقط برای اتصال و فایل‌هاست. ایده، ساخت پست و برنامه‌ریزی را
          در همان گفتگوی ChatGPT انجام بده.
        </p>
      </section>
      <div className="card">
        <h2>{connected ? "اتصال آماده است" : "اتصال یک‌باره"}</h2>
        <p>
          در پنل Telegram Agent Control یک کلید با دسترسی محدود OPERATE بساز.
          فقط کانال‌های خودت را مجاز کن و کلید را اینجا وارد کن.
        </p>
        <p className="hint">
          کلید OpenAI یا توکن ربات لازم نیست. رمز مالک را اینجا وارد نکن. کلید
          ذخیره‌شده به مدل یا مرورگر برگردانده نمی‌شود.
        </p>
        <form onSubmit={save}>
          <label htmlFor="key">کلید محدود دستیار</label>
          <input
            id="key"
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            autoComplete="off"
            placeholder="tac_…"
            required
          />
          <button disabled={busy || !key}>
            {busy
              ? "در حال بررسی…"
              : connected
                ? "جایگزینی اتصال"
                : "اتصال امن"}
          </button>
        </form>
        {connected && (
          <button className="secondary" disabled={busy} onClick={disconnect}>
            حذف اتصال این رابط
          </button>
        )}
        <output aria-live="polite">{message}</output>
      </div>
      <div className="card">
        <h2>تأیید انتشار با خودت است</h2>
        <p>
          دستیار پیش‌نویس و زمان انتشار را آماده می‌کند و لینک بررسی می‌دهد. با
          ورود به پنل خودت محتوای دقیق را تأیید می‌کنی؛ سپس سرور در زمان مشخص
          اجرا می‌کند. نوشتن «تأیید» در چت به‌تنهایی تأیید امن سرور نیست.
        </p>
      </div>
      {connected && (
        <div className="card">
          <h2>تصویر پست</h2>
          <p>
            اگر ChatGPT لینک قابل‌دریافت تصویر را در اختیار ابزار نگذارد، همان
            تصویر را یک‌بار اینجا بارگذاری کن. فایل در سرور خودت ذخیره می‌شود.
          </p>
          <label htmlFor="image">PNG، JPEG یا WebP · حداکثر ۱۰ مگابایت</label>
          <input
            id="image"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            disabled={busy}
            onChange={(e) => upload(e.target.files?.[0])}
          />
        </div>
      )}
      <footer>بدون چت جدا · بدون خرید API مدل برای این رابط</footer>
    </main>
  );
}
