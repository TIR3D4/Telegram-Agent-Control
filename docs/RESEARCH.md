# Research and attribution

Reviewed 2026-10-09. These projects informed design decisions; none was installed as a privileged agent skill, and their runtime implementation was not copied into this codebase.

| Source | Files / ideas reviewed | Applied decision |
|---|---|---|
| [Official Telegram Bot API](https://core.telegram.org/bots/api) | Method/type tables, Rich Messages, slideshow, files, permissions | Generate a pinned registry; explicit native method coverage |
| [timoncool/telegram-api-mcp](https://github.com/timoncool/telegram-api-mcp) | `src/method-registry.ts`, `src/telegram-client.ts`, method modules | Declarative discovery; lazy schema retrieval to reduce agent context |
| [nfrelink/telegram-scheduler-bot](https://github.com/nfrelink/telegram-scheduler-bot) | `src/scheduler/engine.py`, executor/timing layout | Persistent schedules, bounded missed-run behavior, explicit execution state |
| [ispy4you/auto-telegram-news](https://github.com/ispy4you/auto-telegram-news) | `app/services/post_lifecycle.py`, schema and tests layout | Central lifecycle transitions and visible publish failures |
| [Zulut30/premium-telegram-emoji](https://github.com/Zulut30/premium-telegram-emoji) | `premium_emoji/selection.py`, developer import guide | Inspect previews before semantic selection; stable role bindings |

The registry is derived from Telegram's public technical interface documentation and preserves official field descriptions/source links. It is not an endorsement by Telegram. Other projects retain their own licenses. No emoji artwork is redistributed.

The README banner was generated specifically for this project using the built-in ImageGen tool. Prompt: a wide dark navy developer-platform banner, exact title “TELEGRAM AGENT CONTROL”, tagline “Publish. Schedule. Automate.”, minimal glass modules for publishing, time, workflow and terminal.
