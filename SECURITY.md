# Security

Never publish bot tokens, owner/agent keys, `.env`, database dumps or user media. The gateway binds locally by default; use HTTPS for remote access. Owner credentials approve changes; agent credentials cannot approve their own operations. Rotate exposed credentials in their issuing service.

Report a vulnerability privately using GitHub private vulnerability reporting if enabled. Otherwise contact the repository owner privately first; do not open a public issue containing an exploit against a live installation or secrets.

This initial release has automated tests but has not received an independent security audit. See `docs/VALIDATION.md` for tested boundaries. Back up before upgrades, and use a test channel before production rollout.
