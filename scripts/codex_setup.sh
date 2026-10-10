#!/usr/bin/env bash
# Development dependencies only. Never reads production secrets or starts services.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
python3 -c 'import sys; assert sys.version_info >= (3, 12), "Python 3.12+ required"'
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
printf '%s\n' 'Development dependencies ready. Run: .venv/bin/python -m pytest -q' 'Browser checks additionally require npm ci and Playwright browser installation; see docs/CODEX_HANDOFF.md.'
