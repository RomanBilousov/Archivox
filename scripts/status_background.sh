#!/bin/zsh
set -euo pipefail

PID_FILE="/tmp/archivox-web.pid"
PORT="${ARCHIVOX_PORT:-8420}"
LISTENER_PID="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"

if [[ -n "$LISTENER_PID" ]]; then
  echo "$LISTENER_PID" >"$PID_FILE"
  echo "Archivox is running on PID $LISTENER_PID"
  echo "Open: http://127.0.0.1:$PORT"
  exit 0
fi

rm -f "$PID_FILE"
echo "Archivox is not running"
