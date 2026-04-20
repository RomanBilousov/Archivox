#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
find_uv_bin() {
  local candidates=(
    "${UV_BIN:-}"
    "$(command -v uv 2>/dev/null || true)"
    "$HOME/.local/bin/uv"
    "/opt/homebrew/bin/uv"
    "/usr/local/bin/uv"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

UV_BIN="$(find_uv_bin)" || {
  echo "uv binary not found. Install uv first or pass UV_BIN=/absolute/path/to/uv." >&2
  exit 1
}

cd "$ROOT_DIR"
exec "$UV_BIN" run archivox
