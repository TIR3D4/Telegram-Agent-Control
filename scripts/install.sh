#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
command -v python3 >/dev/null || { printf '%s\n' 'Install Python 3 first (used only for setup).'; exit 1; }
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  printf '%s\n' 'Docker Engine and Compose v2 are required.' 'Install official Docker packages: https://docs.docker.com/engine/install/'
  read -r -p 'Run the official Docker convenience installer now? [y/N] ' answer
  [[ "$answer" == y || "$answer" == Y ]] || exit 1
  [[ "$(id -u)" == 0 ]] || { printf '%s\n' 'Run setup with sudo to install Docker.'; exit 1; }
  command -v curl >/dev/null || { printf '%s\n' 'Install curl first.'; exit 1; }
  temp="$(mktemp)"
  trap 'rm -f "$temp"' EXIT
  curl --fail --show-error --silent --location https://get.docker.com -o "$temp"
  sh "$temp"
fi
exec ./scripts/tacctl install
