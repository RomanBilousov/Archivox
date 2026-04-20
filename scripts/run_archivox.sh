#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
UV_BIN="${UV_BIN:-/opt/homebrew/bin/uv}"

if [[ ! -x "$UV_BIN" ]]; then
  echo "uv binary not found at $UV_BIN" >&2
  exit 1
fi

cd "$ROOT_DIR"
exec "$UV_BIN" run archivox
