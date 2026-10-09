# Security

Never publish bot tokens, owner/agent keys, `.env`, database dumps or user media. The gateway binds locally by default; use HTTPS for remote access. Owner credentials approve changes; agent credentials cannot approve their own operations. Rotate exposed credentials in their issuing service.

Report a vulnerability privately using GitHub private vulnerability reporting if enabled. Otherwise contact the repository owner privately first; do not open a public issue containing an exploit against a live installation or secrets.

Version 0.2 has automated tests but has not received an independent security audit. See [security model](docs/SECURITY.md), [permissions](docs/PERMISSIONS.md) and [test evidence](docs/TEST_RESULTS.md) for tested boundaries. Back up before upgrades, and use a test channel before production rollout.
