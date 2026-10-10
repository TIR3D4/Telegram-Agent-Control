#!/usr/bin/env bash
# Development dependencies only. Never reads production secrets or starts services.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
python_cmd="${PYTHON:-python3}"
if [[ -z "${PYTHON:-}" ]] && ! "$python_cmd" -c 'import sys' >/dev/null 2>&1; then
  python_cmd=python
fi
"$python_cmd" -c 'import sys; assert sys.version_info >= (3, 12), "Python 3.12+ required"'
if [[ ! -d .venv ]]; then
  "$python_cmd" -m venv .venv
fi
venv_python=.venv/bin/python
if [[ -f .venv/Scripts/python.exe ]]; then
  venv_python=.venv/Scripts/python.exe
fi
"$venv_python" -m pip install -r requirements.lock
"$venv_python" -m pip install --no-deps -e .
printf '%s\n' "Development dependencies ready. Run: $venv_python -m pytest -q" 'Browser checks additionally require npm ci and Playwright browser installation; see docs/CODEX_HANDOFF.md.'
