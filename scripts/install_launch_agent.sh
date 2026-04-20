#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_SOURCE="$ROOT_DIR/ops/macos/com.archivox.web.plist"
PLIST_TARGET="$HOME/Library/LaunchAgents/com.archivox.web.plist"

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

escape_for_sed() {
  printf '%s' "$1" | sed 's/[&|]/\\&/g'
}

UV_BIN="$(find_uv_bin)" || {
  echo "uv binary not found. Install uv first or pass UV_BIN=/absolute/path/to/uv." >&2
  exit 1
}
PATH_VALUE="$(dirname "$UV_BIN"):/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

mkdir -p "$HOME/Library/LaunchAgents"
ROOT_DIR_ESCAPED="$(escape_for_sed "$ROOT_DIR")"
UV_BIN_ESCAPED="$(escape_for_sed "$UV_BIN")"
PATH_VALUE_ESCAPED="$(escape_for_sed "$PATH_VALUE")"
sed \
  -e "s|__ARCHIVOX_ROOT__|$ROOT_DIR_ESCAPED|g" \
  -e "s|__ARCHIVOX_UV_BIN__|$UV_BIN_ESCAPED|g" \
  -e "s|__ARCHIVOX_PATH__|$PATH_VALUE_ESCAPED|g" \
  "$PLIST_SOURCE" >"$PLIST_TARGET"
launchctl bootout "gui/$(id -u)" "$PLIST_TARGET" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_TARGET"
launchctl enable "gui/$(id -u)/com.archivox.web"

echo "Installed Archivox web LaunchAgent."
echo "Open: http://127.0.0.1:8420"
