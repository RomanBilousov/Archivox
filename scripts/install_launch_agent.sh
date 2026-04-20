#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_SOURCE="$ROOT_DIR/ops/macos/com.archivox.web.plist"
PLIST_TARGET="$HOME/Library/LaunchAgents/com.archivox.web.plist"

escape_for_sed() {
  printf '%s' "$1" | sed 's/[&|]/\\&/g'
}

mkdir -p "$HOME/Library/LaunchAgents"
ROOT_DIR_ESCAPED="$(escape_for_sed "$ROOT_DIR")"
sed "s|__ARCHIVOX_ROOT__|$ROOT_DIR_ESCAPED|g" "$PLIST_SOURCE" >"$PLIST_TARGET"
launchctl bootout "gui/$(id -u)" "$PLIST_TARGET" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_TARGET"
launchctl enable "gui/$(id -u)/com.archivox.web"

echo "Installed Archivox web LaunchAgent."
echo "Open: http://127.0.0.1:8420"
