"""Secret-free, client-specific connection recipes over the shared gateway."""

import json
from urllib.parse import urlsplit


def profiles(public_url: str, oauth: bool) -> list[dict]:
    base = public_url.rstrip("/")
    parsed = urlsplit(base)
    # Configuration is operator-controlled; still never interpolate it as shell code.
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Invalid public origin")
    if parsed.path or parsed.query or parsed.fragment:
        raise ValueError("Public URL must be an origin")
    mcp = base + "/mcp/"
    codex = (
        "[mcp_servers.telegram_control]\nurl = "
        + json.dumps(mcp)
        + '\nbearer_token_env_var = "TAC_TOKEN"\nstartup_timeout_sec = 20\ntool_timeout_sec = 45\n'
    )
    claude = json.dumps(
        {
            "mcpServers": {
                "telegram_control": {
                    "type": "http",
                    "url": mcp,
                    "headers": {"Authorization": "Bearer ${TAC_TOKEN}"},
                }
            }
        },
        indent=2,
    )
    return [
        {
            "id": "api",
            "title": "REST API",
            "subtitle": "ابزارهای HTTP و توسعهٔ اختصاصی",
            "endpoint": base + "/v1",
            "auth": "Scoped Bearer",
            "config": "GET " + base + "/v1/system\nAuthorization: Bearer <SCOPED_TOKEN>",
            "filename": "api-connection.txt",
            "steps": [
                "مجوز محدود ایجاد کنید.",
                "کلید را در مخزن امن ابزار HTTP قرار دهید.",
                "با GET /v1/system هویت را بررسی کنید.",
            ],
            "limitation": "چسباندن آدرس در گفتگو، قابلیت اجرای HTTP به دستیار اضافه نمی‌کند.",
        },
        {
            "id": "mcp",
            "title": "MCP",
            "subtitle": "اتصال استاندارد برای دستیارهای سازگار",
            "endpoint": mcp,
            "auth": "Scoped Bearer / OAuth" if oauth else "Scoped Bearer",
            "config": json.dumps(
                {"url": mcp, "transport": "Streamable HTTP", "authorization": "Bearer <SCOPED_TOKEN>"},
                indent=2,
            ),
            "filename": "mcp-connection.json",
            "steps": [
                "Streamable HTTP را انتخاب کنید.",
                "آدرس و روش احراز هویت را وارد کنید.",
                "initialize، tools/list و inspect_system را اجرا کنید.",
            ],
            "limitation": "این فایل شرح اتصال است؛ قالب فایل تنظیمات هر کلاینت می‌تواند متفاوت باشد.",
        },
        {
            "id": "codex",
            "title": "Codex",
            "subtitle": "CLI و افزونهٔ IDE با MCP",
            "endpoint": mcp,
            "auth": "TAC_TOKEN environment variable",
            "config": codex,
            "filename": "codex-config.toml",
            "steps": [
                "یک کلید محدود برای Codex بسازید و TAC_TOKEN را در محیط اجرای آن تنظیم کنید.",
                "قطعهٔ تنظیمات را به ~/.codex/config.toml اضافه کنید.",
                "در Codex ابزار inspect_system را فراخوانی کنید.",
            ],
            "limitation": "تنظیمات CLI اتصال خودکار در ChatGPT موبایل یا محیط Cloud ایجاد نمی‌کند.",
        },
        {
            "id": "claude",
            "title": "Claude",
            "subtitle": "Claude Web / Mobile و Claude Code",
            "endpoint": mcp,
            "auth": "Scoped Bearer / configured OAuth",
            "config": claude,
            "filename": "claude.mcp.json",
            "steps": [
                "در Claude بخش Connectors یک اتصال سفارشی با این آدرس اضافه کنید.",
                "اگر Request headers در دسترس است، Authorization: Bearer و کلید محدود را وارد کنید؛ در غیر این صورت OAuth ثبت‌شده لازم است.",
                "در Claude Code، فایل را به .mcp.json اضافه و TAC_TOKEN را تنظیم کنید؛ سپس /mcp را بررسی کنید.",
            ],
            "limitation": "فایل .mcp.json مخصوص Claude Code است. اتصال وب از سرورهای Claude برقرار می‌شود و باید جداگانه در حساب فعال شود.",
        },
        {
            "id": "chatgpt",
            "title": "ChatGPT",
            "subtitle": "گفتگو در خود ChatGPT و گوشی",
            "endpoint": mcp,
            "auth": "Registered remote connection / OAuth",
            "config": mcp,
            "filename": "chatgpt-endpoint.txt",
            "steps": [
                "اتصال خصوصی موجود را در همان گفتگوی ChatGPT انتخاب کنید.",
                "برای اتصال مستقیم جدید، امکان ثبت custom MCP باید در حساب میزبان موجود باشد.",
                "پس از اتصال، از دستیار بخواهید inspect_system را اجرا کند.",
            ],
            "limitation": "فایل ZIP یا تغییر DNS محدودیت حساب را رفع نمی‌کند. پل خصوصی موجود جدا از MCP مستقیم است؛ اتصال هر دو باید واقعاً آزمایش شود.",
        },
    ]
