#!/bin/zsh
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Archivox launcher app can only be installed on macOS." >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="Archivox"
APP_DIR="${APP_DIR:-$HOME/Applications}"
APP_PATH="$APP_DIR/$APP_NAME.app"
START_SCRIPT="$ROOT_DIR/scripts/start_background.sh"
PORT="${ARCHIVOX_PORT:-8420}"
APP_URL="http://127.0.0.1:$PORT"
OSACOMPILE_BIN="${OSACOMPILE_BIN:-/usr/bin/osacompile}"

if [[ ! -x "$OSACOMPILE_BIN" ]]; then
  echo "osacompile not found at $OSACOMPILE_BIN" >&2
  exit 1
fi

if [[ ! -f "$START_SCRIPT" ]]; then
  echo "Start script not found at $START_SCRIPT" >&2
  exit 1
fi

mkdir -p "$APP_DIR"
chmod +x "$START_SCRIPT"

escape_for_applescript() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

START_SCRIPT_ESCAPED="$(escape_for_applescript "$START_SCRIPT")"
APP_URL_ESCAPED="$(escape_for_applescript "$APP_URL")"

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

APPLE_SCRIPT_PATH="$TEMP_DIR/archivox-launcher.applescript"
cat >"$APPLE_SCRIPT_PATH" <<EOF
on run
  set startScript to "$START_SCRIPT_ESCAPED"
  set appUrl to "$APP_URL_ESCAPED"

  try
    do shell script "chmod +x " & quoted form of startScript & " && " & quoted form of startScript
    open location appUrl
  on error errMsg number errNum
    display dialog "Archivox could not start." & return & return & errMsg & return & return & "If you moved the repository, run scripts/install_launcher_app.sh again." buttons {"OK"} default button "OK" with icon stop
  end try
end run
EOF

rm -rf "$APP_PATH"
"$OSACOMPILE_BIN" -o "$APP_PATH" "$APPLE_SCRIPT_PATH"

echo "Installed $APP_NAME.app"
echo "Location: $APP_PATH"
echo "Click the app in Applications to start Archivox and open $APP_URL"
